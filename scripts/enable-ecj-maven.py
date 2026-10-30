#!/usr/bin/env python3
"""Makes a Maven build compile with ECJ (plexus-compiler-eclipse) by adding the compiler plugin to the root pom.

usage: enable-ecj-maven.py <pom.xml> <ecj version>
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

POM, ECJ_VERSION = sys.argv[1], sys.argv[2]
PLEXUS_ECLIPSE = "2.15.0"
COMPILER_PLUGIN = "3.13.0"

# keep the comments: some builds read them (Camel's camel-package-maven-plugin looks for "<!-- camel ...: START -->"
# markers in parent/pom.xml and fails with a NullPointerException without them)
tree = ET.parse(POM, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True)))
project = tree.getroot()
ns = project.tag[1:].partition('}')[0] if project.tag.startswith('{') else ''  # a pom may have no namespace
if ns:
    ET.register_namespace('', ns)
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
q = lambda tag: f'{{{ns}}}{tag}' if ns else tag

def child(parent, tag):
    found = parent.find(q(tag))
    if found is None:
        found = ET.SubElement(parent, q(tag))
    return found

def text(parent, tag, value):
    ET.SubElement(parent, q(tag)).text = value

build = child(project, 'build')

def ecj_compiler_args():
    """The projects.json field ecj_compiler_args: a JSON list of strings, or nothing."""
    value = os.environ.get('ECJ_COMPILER_ARGS')
    if not value:
        return []
    try:
        args = json.loads(value)
    except ValueError:
        args = None
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        sys.exit(f'ecj_compiler_args must be a list of strings: {value}')
    return args

ECJ_ARGS = ecj_compiler_args()
# the compiler plugins of the pluginManagement sections: the ECJ arguments go to the plugins of the builds only
MANAGED = {plugin for management in project.iter(q('pluginManagement')) for plugin in management.iter(q('plugin'))}
IN_PROFILES = {plugin for profile in project.iter(q('profile')) for plugin in profile.iter(q('plugin'))}

def add_ecj(plugin):
    """Adds the ECJ dependencies and compilerId to a compiler plugin, keeping its other configuration."""
    dependencies = child(plugin, 'dependencies')
    for dependency in list(dependencies.findall(q('dependency'))):
        if dependency.findtext(q('artifactId')) in ('plexus-compiler-eclipse', 'ecj'):
            dependencies.remove(dependency)
    for group, artifact, version in (('org.codehaus.plexus', 'plexus-compiler-eclipse', PLEXUS_ECLIPSE),
                                     ('org.eclipse.jdt', 'ecj', ECJ_VERSION)):
        dependency = ET.SubElement(dependencies, q('dependency'))
        text(dependency, 'groupId', group)
        text(dependency, 'artifactId', artifact)
        text(dependency, 'version', version)
    configuration = child(plugin, 'configuration')
    for old in configuration.findall(q('compilerId')):
        configuration.remove(old)
    text(configuration, 'compilerId', 'eclipse')
    if os.environ.get('ECJ_NO_MODULE_PATH'):
        # ECJ's javax.tools compiler ignores --patch-module (EclipseCompilerImpl.setPaths does not call handlePatchModule),
        # so the tests are not patched into the module of the main code
        for old in configuration.findall(q('useModulePath')):
            configuration.remove(old)
        text(configuration, 'useModulePath', 'false')
        # test sources with their own module-info.java (Logback) are modules of their own: compile them as plain classes
        for old in configuration.findall(q('testExcludes')):
            configuration.remove(old)
        text(ET.SubElement(configuration, q('testExcludes')), 'testExclude', '**/module-info.java')
        # the main module-info.java too: its dependencies are on the class path, so the module cannot read them
        for old in configuration.findall(q('excludes')):
            configuration.remove(old)
        text(ET.SubElement(configuration, q('excludes')), 'exclude', '**/module-info.java')
    if os.environ.get('ECJ_OVERRIDE_COMPILER_ARGS'):
        # javac only arguments that a remote parent pom sets in the executions (Log4j: ErrorProne options): replace them
        executions = child(plugin, 'executions')
        for execution_id in ('default-compile', 'default-testCompile'):
            execution = next((e for e in executions.findall(q('execution')) if e.findtext(q('id')) == execution_id), None)
            if execution is None:
                execution = ET.SubElement(executions, q('execution'))
                text(execution, 'id', execution_id)
            execution_configuration = child(execution, 'configuration')
            for old in execution_configuration.findall(q('compilerArgs')):
                execution_configuration.remove(old)
            ET.SubElement(execution_configuration, q('compilerArgs'), {'combine.self': 'override'})
    # a recent compiler plugin: old ones fail with plexus-compiler-eclipse (API incompatibility, or version 4.0.0-beta resolved)
    version = plugin.find(q('version'))
    if version is None:
        text(plugin, 'version', COMPILER_PLUGIN)
    elif version.text and (version.text.startswith('${') or tuple(int(x) for x in re.findall(r'\d+', version.text)[:3] + [0, 0, 0])[:3] < (3, 13, 0)):
        version.text = COMPILER_PLUGIN
    for fail in configuration.findall(q('failOnWarning')):
        fail.text = 'false'
    # javac only options that the ECJ batch compiler rejects
    for args in plugin.iter(q('compilerArgs')):
        for arg in list(args):
            if isinstance(arg.tag, str) and (arg.text or '').startswith(('--should-stop', '-Xplugin', '-XDcompilePolicy', '-Werror', '-Xlint', '-Xdoclint')):
                args.remove(arg)
    if ECJ_ARGS and plugin not in MANAGED:
        add_ecj_args(plugin, configuration)

def add_ecj_args(plugin, configuration):
    """Adds the projects.json ecj_compiler_args (WildFly: where the JBoss Logging processor looks for the translation
    files; without it the processor asks Filer.getResource for a file that does not exist, which javac allows).

    They are appended (Maven merges the <arg> lists of a pom and its parents by position), so every pom of a hierarchy
    adds them once more: an argument must allow repetition. An execution with its own compilerArgs, the override of
    override_compiler_args included, does not see the plugin level ones: it gets them too. The executions that a remote
    parent defines with compilerArgs are not covered. compile and testCompile get the same arguments."""
    lists = [configuration.find(q('compilerArgs'))]
    if lists[0] is None:
        lists = [ET.SubElement(configuration, q('compilerArgs'), {'combine.children': 'append'})]
    lists += plugin.findall(f"{q('executions')}/{q('execution')}/{q('configuration')}/{q('compilerArgs')}")
    for args in lists:
        for value in ECJ_ARGS:
            text(args, 'arg', value)

def compiler_plugins(plugins):
    return [p for p in plugins.findall(q('plugin')) if p.findtext(q('artifactId')) == 'maven-compiler-plugin']

def new_compiler(plugins):
    plugin = ET.SubElement(plugins, q('plugin'))
    text(plugin, 'groupId', 'org.apache.maven.plugins')
    text(plugin, 'artifactId', 'maven-compiler-plugin')
    return plugin

# every maven-compiler-plugin of the pom: build, pluginManagement and profiles
declared = [p for p in project.iter(q('plugin')) if p.findtext(q('artifactId')) == 'maven-compiler-plugin']
for plugin in declared:
    add_ecj(plugin)
    # an execution (or a profile) that sets its own compiler would win over the plugin level setting
    for compiler in plugin.iter(q('compilerId')):
        compiler.text = 'eclipse'
# A pom packaging (a parent or an aggregator) compiles nothing: a compiler plugin in its build would run the compiler
# executions it inherits (PMD's pmd-scala-common, whose sources the pmd-scala_2.1x modules compile), so the plugin goes
# to its pluginManagement, which its children inherit (and every pom of the build is rewritten anyway).
if (project.findtext(q('packaging')) or '').strip() == 'pom':
    if all(plugin in IN_PROFILES for plugin in declared):
        plugin = new_compiler(child(child(build, 'pluginManagement'), 'plugins'))
        MANAGED.add(plugin)  # not a plugin of the build: no ECJ arguments
        add_ecj(plugin)
else:
    plugins = child(build, 'plugins')
    if not compiler_plugins(plugins):
        add_ecj(new_compiler(plugins))
tree.write(POM, encoding='UTF-8', xml_declaration=True)
print(f'{POM}: compiling with ECJ {ECJ_VERSION}')
