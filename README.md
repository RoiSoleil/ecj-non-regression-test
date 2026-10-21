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

## Status

The goal is that every project compiles with ECJ without any compile error. The table says, for each project, whether
it compiles today (`❌` lists compile errors of the compiler itself, `⚠️` a build problem that is not a compile error,
for example a plugin that fails before the compilation). Each failing case has to be analysed one by one: a build
configuration problem is fixed in `projects.json` or in the scripts, a real ECJ bug gets an issue.
Regenerate the table with `python3 scripts/readme-status.py results baseline head` after a run.

<!-- status:start -->
| Project | Released ECJ | Head ECJ |
|---|---|---|
| JDK | ❌ 1 compile errors | ❌ 1 compile errors |
| ApacheCommonsIO | ✅ compiles | ✅ compiles |
| ApacheCommonsCollections | ✅ compiles | ✅ compiles |
| ApacheCommonsLang | ✅ compiles | ✅ compiles |
| JacksonDatabind | ✅ compiles | ✅ compiles |
| xwiki | ✅ compiles | ✅ compiles |
| Eclipse-Collections | ❌ 1 compile errors | ❌ 1 compile errors |
| JavaHamcrest | ✅ compiles | ✅ compiles |
| Quarkus | ⚠️ not run | ⚠️ not run |
| Camel | ⚠️ not run | ⚠️ not run |
| WildFly | ⚠️ not run | ⚠️ not run |
| Guava | ⚠️ not run | ⚠️ not run |
| Gson | ❌ 30 compile errors | ⚠️ not run |
| Guice | ⚠️ not run | ⚠️ not run |
| AssertJ | ⚠️ not run | ⚠️ not run |
| ApacheCommonsMath | ⚠️ not run | ⚠️ not run |
| ApacheCommonsCompress | ⚠️ not run | ⚠️ not run |
| ApacheCommonsCodec | ⚠️ not run | ⚠️ not run |
| Netty | ⚠️ not run | ⚠️ not run |
| ApacheMaven | ⚠️ not run | ⚠️ not run |
| Jsoup | ⚠️ not run | ⚠️ not run |
| Jetty | ⚠️ not run | ⚠️ not run |
| CommonsBeanutils | ⚠️ not run | ⚠️ not run |
| CommonsCli | ⚠️ not run | ⚠️ not run |
| CommonsCsv | ⚠️ not run | ⚠️ not run |
| CommonsText | ⚠️ not run | ⚠️ not run |
| CommonsNet | ⚠️ not run | ⚠️ not run |
| CommonsPool | ⚠️ not run | ⚠️ not run |
| CommonsDbcp | ⚠️ not run | ⚠️ not run |
| CommonsValidator | ⚠️ not run | ⚠️ not run |
| CommonsJexl | ⚠️ not run | ⚠️ not run |
| CommonsConfiguration | ⚠️ not run | ⚠️ not run |
| CommonsFileupload | ⚠️ not run | ⚠️ not run |
| CommonsVfs | ⚠️ not run | ⚠️ not run |
| CommonsBcel | ⚠️ not run | ⚠️ not run |
| CommonsExec | ⚠️ not run | ⚠️ not run |
| CommonsImaging | ⚠️ not run | ⚠️ not run |
| CommonsRng | ⚠️ not run | ⚠️ not run |
| CommonsNumbers | ⚠️ not run | ⚠️ not run |
| CommonsStatistics | ⚠️ not run | ⚠️ not run |
| CommonsGeometry | ⚠️ not run | ⚠️ not run |
| CommonsLogging | ⚠️ not run | ⚠️ not run |
| CommonsEmail | ⚠️ not run | ⚠️ not run |
| CommonsDigester | ⚠️ not run | ⚠️ not run |
| LoggingLog4j2 | ⚠️ not run | ⚠️ not run |
| Shiro | ⚠️ not run | ⚠️ not run |
| Curator | ⚠️ not run | ⚠️ not run |
| JacksonCore | ⚠️ not run | ⚠️ not run |
| JacksonAnnotations | ⚠️ not run | ⚠️ not run |
| Mybatis3 | ⚠️ not run | ⚠️ not run |
| JSqlParser | ⚠️ not run | ⚠️ not run |
| Javaparser | ⚠️ not run | ⚠️ not run |
| Pmd | ⚠️ not run | ⚠️ not run |
| Junit4 | ⚠️ not run | ⚠️ not run |
| Slf4j | ❌ 419 compile errors | ⚠️ not run |
| Logback | ⚠️ not run | ⚠️ not run |
| H2database | ⚠️ not run | ⚠️ not run |
| Dropwizard | ⚠️ not run | ⚠️ not run |
| Jdbi | ⚠️ not run | ⚠️ not run |
| RestAssured | ⚠️ not run | ⚠️ not run |
| Pdfbox | ⚠️ not run | ⚠️ not run |
| Activemq | ⚠️ not run | ⚠️ not run |
| Avro | ⚠️ not run | ⚠️ not run |
| MavenSurefire | ⚠️ not run | ⚠️ not run |
| HttpcomponentsClient | ⚠️ not run | ⚠️ not run |
| HttpcomponentsCore | ✅ compiles | ⚠️ not run |
| Zookeeper | ⚠️ not run | ⚠️ not run |
| Tika | ⚠️ not run | ⚠️ not run |
| VelocityEngine | ⚠️ not run | ⚠️ not run |
| HibernateValidator | ⚠️ not run | ⚠️ not run |
| Checkstyle | ✅ compiles | ⚠️ not run |
<!-- status:end -->

## How it works

1. `scripts/build-ecj.sh` compiles the ECJ batch compiler of an `eclipse.jdt.core` checkout into a jar (a few
   seconds, no Tycho) and gives it a version and the `JavaCompiler` service entry that `plexus-compiler-eclipse` needs.
2. `scripts/enable-ecj-maven.py` switches a Maven build to ECJ (`plexus-compiler-eclipse`) without dropping the
   project's own compiler configuration. Gradle projects use a patch from `patches/`.
3. `scripts/run-project.sh <project> <label> <ECJ version>` builds one project and records its status
   (`results/<project>-<label>.status`) and one normalized line per compile error (`.errors`). A Maven build that never
   printed `Compiling with eclipse` is reported as `ecj not used`.
4. `scripts/compare.py` compares the `baseline` and `head` runs. It fails when the head ECJ gives errors the baseline
   does not, when a project that builds with the baseline does not build with head.
   A project that does not build with the baseline ECJ, or that was not tested at all
   (clone or patch failure), is shown with `⚠️` in the table but does not fail the run: only new problems do.

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

* Joda-Time is not tested: its sources are Java 1.5, which a current ECJ no longer accepts.

* Only the root `pom.xml` is switched to ECJ. A module that sets its own `compilerId` (or a profile-scoped compiler
  plugin) still compiles with javac; the run only checks that at least one module reported `Compiling with eclipse`.
* Gradle projects (JavaHamcrest) are not checked for ECJ use.
* Errors are compared as `path:line message`; a reworded diagnostic shows as one new and one vanished error.
* A project that already fails with the baseline ECJ (Eclipse Collections: `$deserializeLambda$` exceeds 64 KB) only
  detects new compile error lines, not new crashes.
* The head ECJ is built from the batch compiler sources only, with a fake version `3.99.0`. The annotation processing
  classes are compiled with JDK 25 and run on JDK 21.

This repository was written with the help of Claude (AI).
