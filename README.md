# ECJ non-regression test

Compiles real open source projects with the latest `eclipse.jdt.core` compiler (ECJ, built from `master`) and with the
last released ECJ, and reports the compile errors that only the new compiler gives. It catches the regressions that
the compiler's own test suite does not: valid code in the wild that a recent change makes ECJ reject.

## What is built

| Project | How |
|---|---|
| JDK (`java.base`, `java.xml`, `java.net.http`, `java.desktop`) | batch compiler on the sources of the runner's JDK (`src.zip`) |
| Apache Commons IO, Lang, Collections, Math, Compress, Codec | Maven |
| Jackson Databind, Gson, Guava, Guice, AssertJ, Joda-Time, jsoup, Jetty, Netty, Apache Maven | Maven |
| XWiki Commons | Maven |
| 49 more Maven projects: Apache Commons (BeanUtils, CLI, CSV, Text, Net, Pool, DBCP, Validator, JEXL, Configuration, FileUpload, VFS, BCEL, Exec, Imaging, RNG, Numbers, Statistics, Geometry, Logging, Email, Digester), HttpComponents, Log4j 2, Shiro, ZooKeeper, Curator, Velocity, Jackson core and annotations, MyBatis, Hibernate Validator, JSqlParser, JavaParser, Checkstyle, PMD, JUnit 4, SLF4J, Logback, H2, Dropwizard, JDBI, REST Assured, Tika, PDFBox, ActiveMQ, Avro, Maven Surefire | Maven (see `projects.json` for the exact list and commits) |
| Eclipse Collections | Maven (`install`) |
| JavaHamcrest | Gradle (ECJ Gradle plugin, see `patches/`) |
| Quarkus, Camel, WildFly | Maven (`install`, several hours: the baseline and the head ECJ run in two parallel jobs) |

Every project is pinned to a commit (`projects.json`), so the known errors stay the same from one run to the next.
Update the pins in a pull request.

## How it works

1. `scripts/build-ecj.sh` compiles the ECJ batch compiler of an `eclipse.jdt.core` checkout into a jar (a few
   seconds, no Tycho) and gives it a version and the `JavaCompiler` service entry that `plexus-compiler-eclipse` needs.
2. `scripts/enable-ecj-maven.py` switches a Maven build to ECJ (`plexus-compiler-eclipse`) without dropping the
   project's own compiler configuration. Gradle projects use a patch from `patches/`.
3. `scripts/run-project.sh <project> <label> <ECJ version>` builds one project and records its status
   (`results/<project>-<label>.status`) and one normalized line per compile error (`.errors`). A Maven build that never
   printed `Compiling with eclipse` is reported as `ecj not used`.
4. `scripts/compare.py` compares the `baseline` and `head` runs. It fails when the head ECJ gives errors the baseline
   does not, when a project that builds with the baseline does not build with head, or when a project was not tested
   at all (clone or patch failure).

The workflow `ECJ Non-regression Builds` (`.github/workflows/ecj-matrix.yml`) runs two jobs per project (baseline and head ECJ, in parallel) and a final `compare` job. The
`ECJ Commit Watcher` workflow (`ecj-check.yml`) runs it every night when `eclipse.jdt.core` has a new commit; a
successfully tested commit gets a `tested/<sha>` tag, a failing run is retried the next night.

## Run it

*Actions > ECJ Non-regression Builds > Run workflow*

* `ecj_ref`: branch, tag or commit of `eclipse.jdt.core` (a pull request head works: `refs/pull/<n>/head`).
  Default: `master`.
* `baseline`: released ECJ version to compare with (default: the latest release on Maven Central).
* `projects`: comma separated names, for example `Quarkus,Camel`. Default: all projects.

The summary of each job shows the table of the run and, for each project, the new and the vanished errors.

Locally (JDK 21, Maven 3.9.9 or later, `jq`):

```bash
scripts/build-ecj.sh ~/git/eclipse.jdt.core ecj-head.jar
mvn -B -q install:install-file -Dfile=ecj-head.jar -DgroupId=org.eclipse.jdt -DartifactId=ecj \
    -Dversion=HEAD-SNAPSHOT -Dpackaging=jar
scripts/run-project.sh ApacheCommonsLang baseline 3.46.100
scripts/run-project.sh ApacheCommonsLang head HEAD-SNAPSHOT
python3 scripts/compare.py results baseline head
```

The JDK project needs a JDK with `lib/src.zip`; otherwise set `JDK_SRC_DIR` to a directory with one folder per module
(and `JDK_MODULES` to choose the modules).

## Known limits

* Only the root `pom.xml` is switched to ECJ. A module that sets its own `compilerId` (or a profile-scoped compiler
  plugin) still compiles with javac; the run only checks that at least one module reported `Compiling with eclipse`.
* Gradle projects (JavaHamcrest) are not checked for ECJ use.
* Errors are compared as `path:line message`; a reworded diagnostic shows as one new and one vanished error.
* A project that already fails with the baseline ECJ (Eclipse Collections: `$deserializeLambda$` exceeds 64 KB) only
  detects new compile error lines, not new crashes.
* The head ECJ is built from the batch compiler sources only, with a fake version `3.99.0`. The annotation processing
  classes are compiled with JDK 25 and run on JDK 21.

This repository was written with the help of Claude (AI).
