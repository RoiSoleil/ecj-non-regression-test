#!/usr/bin/env python3
"""Makes a Maven build compile with ECJ (plexus-compiler-eclipse) by adding the compiler plugin to the root pom.

usage: enable-ecj-maven.py <pom.xml> <ecj version, or merapi>
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

POM, ECJ_VERSION = sys.argv[1], sys.argv[2]
PLEXUS_ECLIPSE = "2.15.0"
COMPILER_PLUGIN = "3.13.0"
MERAPI = ECJ_VERSION == 'merapi'
MERAPI_JAVAC = os.environ.get('MERAPI_JAVAC', '')
if MERAPI and not MERAPI_JAVAC:
    sys.exit('MERAPI_JAVAC must give the javac executable of Merapi')

# keep the comments: some builds read them (Camel's camel-package-maven-plugin looks for "<!-- camel ...: START -->"
# markers in parent/pom.xml and fails with a NullPointerException without them)
with open(POM, 'rb') as source:
    original = source.read()
xml_parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
xml_parser.feed(original)
tree = ET.ElementTree(xml_parser.close())
project = tree.getroot()
ns = project.tag[1:].partition('}')[0] if project.tag.startswith('{') else ''  # a pom may have no namespace
if ns:
    ET.register_namespace('', ns)
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
NESTED_NAMESPACES = {}
for prefix, uri in re.findall(rb'xmlns:([A-Za-z_][\w.-]*)\s*=\s*["\']([^"\']+)["\']', original):
    prefix, uri = prefix.decode(), uri.decode()
    if prefix != 'xsi' and not re.fullmatch(r'ns\d+', prefix) and uri not in (ns, 'http://www.w3.org/2001/XMLSchema-instance'):
        ET.register_namespace(prefix, uri)
        NESTED_NAMESPACES[prefix] = uri
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
LOMBOK = bool(os.environ.get('ECJ_LOMBOK'))
JVM_ARGS_FILE = os.environ.get('ECJ_JVM_ARGS_FILE')
PROPERTIES = {}
for properties in [project.find(q('properties'))]:
    if properties is not None:
        for prop in properties:
            if isinstance(prop.tag, str):
                PROPERTIES.setdefault(prop.tag.rpartition('}')[2], (prop.text or '').strip())

def resolve(value):
    for _ in range(5):
        match = re.fullmatch(r'\$\{([^}]+)\}', value)
        if not match or match.group(1) not in PROPERTIES:
            break
        value = PROPERTIES[match.group(1)]
    return value

def java_level(value):
    value = resolve((value or '').strip())
    match = re.match(r'(?:1\.)?(\d+)', value)
    return int(match.group(1)) if match else None

def effective_compiler_executions():
    path = os.environ.get('ECJ_EFFECTIVE_POM')
    if not path or not os.path.isfile(path):
        return {}
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return {}
    artifact = (project.findtext(q('artifactId')) or '').strip()
    group = (project.findtext(q('groupId')) or project.findtext(f"{q('parent')}/{q('groupId')}") or '').strip()
    candidates = [e for e in root.iter() if isinstance(e.tag, str) and e.tag.rpartition('}')[2] == 'project']
    for candidate in candidates:
        ens = candidate.tag[1:].partition('}')[0] if candidate.tag.startswith('{') else ''
        eq = lambda tag, ens=ens: f'{{{ens}}}{tag}' if ens else tag
        if (candidate.findtext(eq('artifactId')) or '').strip() != artifact:
            continue
        if group and (candidate.findtext(eq('groupId')) or '').strip() != group:
            continue
        found = {}
        for tag in ('release', 'target', 'source'):
            EFFECTIVE_LEVELS.append(candidate.findtext(f"{eq('properties')}/{eq('maven.compiler.' + tag)}"))
        EFFECTIVE_PROC.append(candidate.findtext(f"{eq('properties')}/{eq('maven.compiler.proc')}") or '')
        for plugin in candidate.findall(f"{eq('build')}/{eq('plugins')}/{eq('plugin')}"):
            if plugin.findtext(eq('artifactId')) != 'maven-compiler-plugin':
                continue
            for tag in ('release', 'target', 'source'):
                EFFECTIVE_LEVELS.append(plugin.findtext(f"{eq('configuration')}/{eq(tag)}"))
            for execution in plugin.findall(f"{eq('executions')}/{eq('execution')}"):
                args = execution.find(f"{eq('configuration')}/{eq('compilerArgs')}")
                if args is not None:
                    values = [(arg.text or '').strip() for arg in args if isinstance(arg.tag, str)]
                    proc = (execution.findtext(f"{eq('configuration')}/{eq('proc')}") or '').strip()
                    if proc in ('none', 'only') and f'-proc:{proc}' not in values:
                        values.append(f'-proc:{proc}')
                    found[(execution.findtext(eq('id')) or '').strip()] = values
        return found
    return {}

EFFECTIVE_LEVELS = []
EFFECTIVE_PROC = []
EFFECTIVE_EXECUTIONS = effective_compiler_executions()
# the compiler plugins of the pluginManagement sections: the ECJ arguments go to the plugins of the builds only
MANAGED = {plugin for management in project.iter(q('pluginManagement')) for plugin in management.iter(q('plugin'))}
IN_PROFILES = {plugin for profile in project.iter(q('profile')) for plugin in profile.iter(q('plugin'))}

def add_ecj(plugin):
    """Adds the ECJ dependencies and compilerId to a compiler plugin, keeping its other configuration."""
    dependencies = child(plugin, 'dependencies')
    for dependency in list(dependencies.findall(q('dependency'))):
        artifact = (dependency.findtext(q('artifactId')) or '').strip()
        if artifact in ('ecj', 'tycho-compiler-jdt') or artifact.startswith('plexus-compiler-'):
            dependencies.remove(dependency)
    added = [('org.codehaus.plexus', 'plexus-compiler-eclipse', PLEXUS_ECLIPSE)]
    if not LOMBOK:
        added.append(('org.eclipse.jdt', 'ecj', ECJ_VERSION))
    for group, artifact, version in added:
        dependency = ET.SubElement(dependencies, q('dependency'))
        text(dependency, 'groupId', group)
        text(dependency, 'artifactId', artifact)
        text(dependency, 'version', version)
        if LOMBOK and artifact == 'plexus-compiler-eclipse':
            exclusion = ET.SubElement(child(dependency, 'exclusions'), q('exclusion'))
            text(exclusion, 'groupId', 'org.eclipse.jdt')
            text(exclusion, 'artifactId', 'ecj')
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
    level = max(filter(None, [java_level(configuration.findtext(q(tag))) for tag in ('release', 'target', 'source')]
                       + [java_level(PROPERTIES.get(f'maven.compiler.{tag}')) for tag in ('release', 'target', 'source')]
                       + [java_level(value) for value in EFFECTIVE_LEVELS]),
                default=None)
    configurations = [configuration] + plugin.findall(f"{q('executions')}/{q('execution')}/{q('configuration')}")
    for config in configurations:
        for fail in config.findall(q('failOnWarning')):
            config.remove(fail)
        text(config, 'failOnWarning', 'false')
    if plugin not in MANAGED and plugin not in IN_PROFILES:
        override_effective_args(plugin, level)
    for args in plugin.iter(q('compilerArgs')):
        clean_compiler_args(args, level)
    for config in configurations:
        if config.find(q('includes')) is not None:
            execution = next((e for e in plugin.findall(f"{q('executions')}/{q('execution')}")
                              if e.find(q('configuration')) is config), None)
            goals = ' '.join(g.text or '' for g in execution.iter(q('goal'))) if execution is not None else ''
            execution_id = execution.findtext(q('id')) if execution is not None else ''
            test = 'testCompile' in goals or 'testCompile' in (execution_id or '')
            if execution is None:
                executions = child(plugin, 'executions')
                execution = next((e for e in executions.findall(q('execution'))
                                  if (e.findtext(q('id')) or '').strip() == 'default-compile'), None)
                if execution is None:
                    execution = ET.SubElement(executions, q('execution'))
                    text(execution, 'id', 'default-compile')
                config = child(execution, 'configuration')
            args = config.find(q('compilerArgs'))
            if args is None:
                args = ET.SubElement(config, q('compilerArgs'), {'combine.children': 'append'})
            if '-sourcepath' not in [(arg.text or '').strip() for arg in args if isinstance(arg.tag, str)]:
                text(args, 'arg', '-sourcepath')
                text(args, 'arg', '${project.build.testSourceDirectory}' if test else '${project.build.sourceDirectory}')
    add_proc_args(plugin, configuration)
    if ECJ_ARGS and plugin not in MANAGED:
        add_ecj_args(plugin, configuration)

def add_merapi(plugin):
    configuration = child(plugin, 'configuration')
    settings = (('compilerId', 'javac'), ('fork', 'true'), ('executable', MERAPI_JAVAC))
    for config in [configuration] + plugin.findall(f"{q('executions')}/{q('execution')}/{q('configuration')}"):
        if config is not configuration and not any(config.find(q(tag)) is not None for tag, _ in settings):
            continue
        for tag, value in settings:
            for old in config.findall(q(tag)):
                config.remove(old)
            text(config, tag, value)

def override_effective_args(plugin, level):
    for execution_id, values in EFFECTIVE_EXECUTIONS.items():
        if os.environ.get('ECJ_OVERRIDE_COMPILER_ARGS') and execution_id in ('default-compile', 'default-testCompile'):
            continue
        effective = ET.Element(q('compilerArgs'))
        for value in values:
            text(effective, 'arg', value)
        clean_compiler_args(effective, level)
        cleaned = [(arg.text or '').strip() for arg in effective if isinstance(arg.tag, str)]
        if cleaned == values:
            continue
        executions = child(plugin, 'executions')
        execution = next((e for e in executions.findall(q('execution')) if (e.findtext(q('id')) or '').strip() == execution_id), None)
        if execution is None:
            execution = ET.SubElement(executions, q('execution'))
            text(execution, 'id', execution_id)
        execution_configuration = child(execution, 'configuration')
        for old in execution_configuration.findall(q('compilerArgs')):
            execution_configuration.remove(old)
        args = ET.SubElement(execution_configuration, q('compilerArgs'), {'combine.self': 'override'})
        for value in cleaned:
            text(args, 'arg', value)

def clean_compiler_args(args, level=None):
    """Adapts a compilerArgs list to the ECJ batch compiler, which rejects the javac only options."""
    drop_value = False
    jvm_option = None
    for arg in list(args):
        if not isinstance(arg.tag, str):  # a comment
            continue
        value = resolve((arg.text or '').strip())
        if jvm_option is not None and value.startswith('-J'):
            if JVM_ARGS_FILE and '${' not in value:
                with open(JVM_ARGS_FILE, 'a') as jvm_args:
                    jvm_args.write(f'{jvm_option}={value[2:]}\n')
            jvm_option = None
            args.remove(arg)
            continue
        jvm_option = None
        if drop_value:
            drop_value = False
            args.remove(arg)
        elif value in ('-h', '-Xmaxerrs', '-Xmaxwarns', '--add-opens') or (value == '-extdirs' and level is not None and level >= 9):
            drop_value = True
            args.remove(arg)
        elif value.startswith('--add-opens='):
            args.remove(arg)
        elif value.startswith('-J'):
            if value[2:] in ('--add-opens', '--add-exports', '--add-modules', '--add-reads'):
                jvm_option = value[2:]
            elif JVM_ARGS_FILE and '${' not in value and value[2:].startswith(('--add-opens=', '--add-exports=', '--add-modules=', '--add-reads=')):
                with open(JVM_ARGS_FILE, 'a') as jvm_args:
                    jvm_args.write(value[2:] + '\n')
            args.remove(arg)
        elif not value or value.startswith(('--should-stop', '-Xplugin', '-XD', '-Werror', '-Xlint', '-Xdoclint')):
            # an element without a value (Jersey: <XDignore.symbol.file />) reaches plexus-compiler-eclipse as a null argument
            args.remove(arg)
        elif value.startswith(('--add-exports=', '--add-reads=', '--add-modules=', '--module-version=', '--release=',
                               '--limit-modules=', '--module-path=', '--class-path=', '--source-path=', '--patch-module=')):
            option, _, module = value.partition('=')
            arg.text = option
            following = ET.Element(arg.tag)
            following.text = module
            following.tail = arg.tail
            args.insert(list(args).index(arg) + 1, following)
    # what stays of an emptied list (a comment, white space) reaches plexus-compiler-eclipse as a null argument (Jersey)
    if not any(isinstance(arg.tag, str) for arg in args):
        for arg in list(args):
            args.remove(arg)
        args.text = None

def add_proc_args(plugin, configuration):
    """Passes <proc>none</proc> (or only) as an argument too: plexus-compiler-eclipse up to 2.18.0 drops it unless
    processors or a processor path are configured as well, and ECJ then runs the processors that it finds on the class
    path (Hibernate Validator's annotation-processor module: its own processor, listed in META-INF/services before it
    is compiled, "Provider ... not found"). Fixed in plexus-compiler 9d3498e519, not released yet."""
    configurations = [configuration] + plugin.findall(f"{q('executions')}/{q('execution')}/{q('configuration')}")
    plugin_proc = resolve((configuration.findtext(q('proc')) or PROPERTIES.get('maven.compiler.proc', '')
                           or next((value for value in EFFECTIVE_PROC if value), '')).strip())
    for config in configurations:
        proc = resolve((config.findtext(q('proc')) or '').strip())
        if not proc and (config is configuration or config.find(q('compilerArgs')) is not None):
            proc = plugin_proc
        if proc not in ('none', 'only'):
            continue
        args = config.find(q('compilerArgs'))
        if args is None:
            args = ET.SubElement(config, q('compilerArgs'), {'combine.children': 'append'})
        if f'-proc:{proc}' not in [(arg.text or '').strip() for arg in args if isinstance(arg.tag, str)]:
            text(args, 'arg', f'-proc:{proc}')

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
    plugin = ET.Element(q('plugin'))
    plugins.insert(0, plugin)
    text(plugin, 'groupId', 'org.apache.maven.plugins')
    text(plugin, 'artifactId', 'maven-compiler-plugin')
    return plugin

# every maven-compiler-plugin of the pom: build, pluginManagement and profiles
declared = [p for p in project.iter(q('plugin')) if p.findtext(q('artifactId')) == 'maven-compiler-plugin']
enable = add_merapi if MERAPI else add_ecj
for plugin in declared:
    enable(plugin)
    # an execution (or a profile) that sets its own compiler would win over the plugin level setting
    for compiler in plugin.iter(q('compilerId')):
        compiler.text = 'javac' if MERAPI else 'eclipse'
# A pom packaging (a parent or an aggregator) compiles nothing: a compiler plugin in its build would run the compiler
# executions it inherits (PMD's pmd-scala-common, whose sources the pmd-scala_2.1x modules compile), so the plugin goes
# to its pluginManagement, which its children inherit (and every pom of the build is rewritten anyway).
if (project.findtext(q('packaging')) or '').strip() == 'pom':
    if all(plugin in IN_PROFILES for plugin in declared):
        plugin = new_compiler(child(child(build, 'pluginManagement'), 'plugins'))
        MANAGED.add(plugin)  # not a plugin of the build: no ECJ arguments
        enable(plugin)
else:
    plugins = child(build, 'plugins')
    if not compiler_plugins(plugins):
        enable(new_compiler(plugins))
# ElementTree drops what comes before and after the root element (the license header that apache-rat and the copyright
# plugins check, the XML declaration that sortpom compares) and writes its own declaration: keep the original ones.
# The prolog: a byte order mark, the declaration, comments, processing instructions and a DOCTYPE (with its internal
# subset); the epilogue: everything after the last end tag of the root element.
def original_text():
    declared = re.match(rb'(?:\xef\xbb\xbf)?\s*<\?xml[^>]*encoding=["\']([^"\']+)', original)
    encoding = declared.group(1).decode('ascii') if declared else 'UTF-8'
    try:
        return original.decode(encoding), encoding
    except (LookupError, UnicodeDecodeError):
        return None, None

text, encoding = original_text()
prolog = epilogue = None
if text is not None:
    prolog = re.match(r'\ufeff?(?:\s|<\?.*?\?>|<!--.*?-->|<!DOCTYPE[^>\[]*(?:\[.*?\])?\s*>)*', text, re.S).group(0)
    ends = list(re.finditer(r'</(?:[\w.-]+:)?project\s*>', text))
    epilogue = text[ends[-1].end():] if ends else None
if prolog is not None and epilogue is not None:
    body = ET.tostring(project, encoding='unicode')
    for prefix, uri in NESTED_NAMESPACES.items():
        declaration = f'xmlns:{prefix}="{uri}"'
        body = re.sub(rf'<([\w.:-]+)((?:\s+[\w.:-]+="[^"]*")*?\s+{re.escape(prefix)}:[\w.-]+="[^"]*"[^>]*)>',
                      lambda m: m.group(0) if declaration in m.group(0) else f'<{m.group(1)} {declaration}{m.group(2)}>', body)
        body = re.sub(rf'<({re.escape(prefix)}:[\w.-]+)(?![^>]*{re.escape(declaration)})(?=[\s/>])',
                      lambda m: f'<{m.group(1)} {declaration}', body)
    with open(POM, 'wb') as target:
        target.write((prolog + body + epilogue).encode(encoding, 'xmlcharrefreplace'))
else:
    # an encoding that Python does not know, or no end tag found: the pom compiles with ECJ all the same
    tree.write(POM, encoding='UTF-8', xml_declaration=True)
print(f'{POM}: compiling with Merapi {MERAPI_JAVAC}' if MERAPI else f'{POM}: compiling with ECJ {ECJ_VERSION}')
