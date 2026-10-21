#!/usr/bin/env python3
"""Makes a Maven build compile with ECJ (plexus-compiler-eclipse) by adding the compiler plugin to the root pom.

usage: enable-ecj-maven.py <pom.xml> <ecj version>
"""
import sys
import xml.etree.ElementTree as ET

POM, ECJ_VERSION = sys.argv[1], sys.argv[2]
PLEXUS_ECLIPSE = "2.15.0"

ns = ET.parse(POM).getroot().tag.partition('}')[0].lstrip('{')
ET.register_namespace('', ns)
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
q = lambda tag: f'{{{ns}}}{tag}' if ns else tag
tree = ET.parse(POM)
project = tree.getroot()

def child(parent, tag):
    found = parent.find(q(tag))
    if found is None:
        found = ET.SubElement(parent, q(tag))
    return found

def text(parent, tag, value):
    ET.SubElement(parent, q(tag)).text = value

build = child(project, 'build')

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

def compiler_plugins(plugins):
    return [p for p in plugins.findall(q('plugin')) if p.findtext(q('artifactId')) == 'maven-compiler-plugin']

managed = build.find(q('pluginManagement'))
managed_plugins = managed.find(q('plugins')) if managed is not None else None
declared = compiler_plugins(managed_plugins) if managed_plugins is not None else []
plugins = child(build, 'plugins')
declared += compiler_plugins(plugins)
for plugin in declared:
    add_ecj(plugin)
if not compiler_plugins(plugins):
    plugin = ET.SubElement(plugins, q('plugin'))
    text(plugin, 'groupId', 'org.apache.maven.plugins')
    text(plugin, 'artifactId', 'maven-compiler-plugin')
    add_ecj(plugin)
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
tree.write(POM, encoding='UTF-8', xml_declaration=True)
print(f'{POM}: compiling with ECJ {ECJ_VERSION}')
