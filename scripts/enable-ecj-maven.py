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

plugins = child(child(project, 'build'), 'plugins')
for existing in plugins.findall(q('plugin')):
    if existing.findtext(q('artifactId')) == 'maven-compiler-plugin':
        plugins.remove(existing)

plugin = ET.SubElement(plugins, q('plugin'))
text(plugin, 'groupId', 'org.apache.maven.plugins')
text(plugin, 'artifactId', 'maven-compiler-plugin')
dependencies = ET.SubElement(plugin, q('dependencies'))
for group, artifact, version in (('org.codehaus.plexus', 'plexus-compiler-eclipse', PLEXUS_ECLIPSE),
                                 ('org.eclipse.jdt', 'ecj', ECJ_VERSION)):
    dependency = ET.SubElement(dependencies, q('dependency'))
    text(dependency, 'groupId', group)
    text(dependency, 'artifactId', artifact)
    text(dependency, 'version', version)
configuration = ET.SubElement(plugin, q('configuration'))
text(configuration, 'compilerId', 'eclipse')
tree.write(POM, encoding='UTF-8', xml_declaration=True)
print(f'{POM}: compiling with ECJ {ECJ_VERSION}')
