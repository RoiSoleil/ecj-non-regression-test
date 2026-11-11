"""The probable cause of a build that javac compiles and ECJ does not, from its compile errors and its build log.

The first rule that matches gives the cause: the rules go from the integration of ECJ in the build (how Maven calls it
through javax.tools, annotation processing, options) to the language itself. A cause is a hint to sort the projects,
not a diagnosis: the log of the project says the rest.
"""
import re

# (cause, where: 'errors', 'log' or 'both' (a regular expression for the log, another one for the errors), rule)
RULES = [
    ('javac option that ECJ rejects', 'log', r'Unrecognized option : '),
    ('Java release that this ECJ does not know', 'log', r'release version \d+ is not supported|source level should be in'),
    ('modular tests: --patch-module ignored by javax.tools', 'errors', r'accessible from more than one module: <unnamed>'),
    ('annotation processing: Filer.getResource throws FileNotFoundException', 'log', r'Resource does not exist : CLASS_OUTPUT'),
    ('annotation processing: processor of the module not found', 'log', r'ServiceConfigurationError: javax\.annotation\.processing\.Processor'),
    ('annotation processing: other failure', 'log', r'Annotation generator had thrown|FilerException|Failed to process: '),
    ('--release does not restrict the JDK API (#5660)', 'errors',
     r'Expression type cannot be a subtype of the Pattern type|The method (suspend|resume|stop)\(\) is undefined'
     r'|init\(java\.applet|Applet cannot be resolved|SecurityManager|java\.security\.acl|APPLET cannot be resolved'
     r'|ACCESS_EXTERNAL_DTD|min\(int, int\) is undefined for the type java\.lang\.Math'),
    ('multi-release sources compiled against the classes (#5650)', 'errors', r'src/main/java(\d+|-mr)/|does not exist or is empty'),
    ('multi-release jar: module descriptor under META-INF/versions (#2774)', 'errors',
     r'tools\.jackson|org\.assertj\.core\.api\.Assertions\.assertThat is not accessible'),
    ('package split between a test and its module', 'errors', r'conflicts with a package accessible from another module'),
    ('annotation processing: generated code missing', 'errors',
     r'generated-(test-)?sources/(test-)?annotations/|src/main/generated/|Converter cannot be resolved|Could not generate'
     r'|Duplicate @ConfigurationProperties'),
    ('type referenced indirectly that javac does not need', 'errors', r'indirectly referenced'),
    ('Scala class files', 'errors', r'scala\.'),
    ('type collides with a package (#4413)', 'errors', r'collides with a package'),
    ('$deserializeLambda$ too large (#5595)', 'errors', r'deserializeLambda|65535'),
    # Lombok in the build and what it generates missing: getters, builders, log, the constructor that sets the final
    # fields (a heuristic: a project with Lombok and another missing type is counted here too)
    ('Lombok (works with ECJ only through its agent)', 'both',
     (r'lombok[/:]', r'is undefined|cannot be resolved|may not have been initialized')),
    ('blank final in a lambda (#5593)', 'errors', r'may not have been initialized'),
    ('name clash on an override with an erasure (#5594)', 'errors', r'Name clash'),
    ('ECJ crash', 'log', r'Internal compiler error|Inconsistent classfile|Unknown source: java\.lang\.NullPointerException'),
    ('error that ECJ does not print', 'log', r'has not written it to its logging'),
    ('generics inference', 'errors',
     r'not applicable for the arguments|Type mismatch: cannot convert|Bound mismatch|is ambiguous|capture#'
     r'|inferred type|[Cc]annot infer|type inference'),
    ('module system', 'errors', r'is not visible|is not accessible'),
    ('missing types or members', 'errors', r'cannot be resolved|is undefined'),
]
COMPILED = [(cause, where, tuple(re.compile(r) for r in rule) if where == 'both' else re.compile(rule))
            for cause, where, rule in RULES]
OTHER = 'other'


def cause(errors, log):
    """errors: the normalized compile errors (text), log: the build log (text). Returns the first cause that matches."""
    for name, where, rule in COMPILED:
        if where == 'both':
            if rule[0].search(log) and rule[1].search(errors):
                return name
        elif rule.search(errors if where == 'errors' else log):
            return name
    return OTHER
