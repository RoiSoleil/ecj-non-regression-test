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
| JDK | ❌ 2 compile errors | ❌ 2 compile errors |
| ApacheCommonsIO | ✅ compiles | ✅ compiles |
| ApacheCommonsCollections | ✅ compiles | ✅ compiles |
| ApacheCommonsLang | ✅ compiles | ✅ compiles |
| JacksonDatabind | ✅ compiles | ✅ compiles |
| xwiki | ✅ compiles | ✅ compiles |
| Eclipse-Collections | ❌ 1 compile errors | ❌ 1 compile errors |
| JavaHamcrest | ✅ compiles | ✅ compiles |
| Quarkus | ❌ 1360 compile errors | ❌ 1360 compile errors |
| Camel | ⚠️ build failed (no compile error) | ⚠️ build failed (no compile error) |
| WildFly | ⚠️ build failed (no compile error) | ⚠️ build failed (no compile error) |
| Guava | ❌ 11 compile errors | ❌ 11 compile errors |
| Gson | ❌ 30 compile errors | ❌ 30 compile errors |
| Guice | ❌ 1 compile errors | ❌ 1 compile errors |
| AssertJ | ❌ 53654 compile errors | ❌ 53654 compile errors |
| ApacheCommonsMath | ✅ compiles | ✅ compiles |
| ApacheCommonsCompress | ✅ compiles | ✅ compiles |
| ApacheCommonsCodec | ✅ compiles | ✅ compiles |
| Netty | ❌ 65 compile errors | ❌ 65 compile errors |
| ApacheMaven | ❌ 245 compile errors | ❌ 245 compile errors |
| Jsoup | ❌ 53 compile errors | ❌ 53 compile errors |
| Jetty | ❌ 153 compile errors | ❌ 153 compile errors |
| CommonsBeanutils | ✅ compiles | ✅ compiles |
| CommonsCli | ✅ compiles | ✅ compiles |
| CommonsCsv | ✅ compiles | ✅ compiles |
| CommonsText | ✅ compiles | ✅ compiles |
| CommonsNet | ✅ compiles | ✅ compiles |
| CommonsPool | ✅ compiles | ✅ compiles |
| CommonsDbcp | ✅ compiles | ✅ compiles |
| CommonsValidator | ✅ compiles | ✅ compiles |
| CommonsJexl | ✅ compiles | ✅ compiles |
| CommonsConfiguration | ✅ compiles | ✅ compiles |
| CommonsFileupload | ✅ compiles | ✅ compiles |
| CommonsVfs | ✅ compiles | ✅ compiles |
| CommonsBcel | ✅ compiles | ✅ compiles |
| CommonsExec | ✅ compiles | ✅ compiles |
| CommonsImaging | ✅ compiles | ✅ compiles |
| CommonsRng | ✅ compiles | ✅ compiles |
| CommonsNumbers | ✅ compiles | ✅ compiles |
| CommonsStatistics | ✅ compiles | ✅ compiles |
| CommonsGeometry | ✅ compiles | ✅ compiles |
| CommonsLogging | ✅ compiles | ✅ compiles |
| CommonsEmail | ✅ compiles | ✅ compiles |
| CommonsDigester | ✅ compiles | ✅ compiles |
| LoggingLog4j2 | ✅ compiles | ✅ compiles |
| Shiro | ❌ 54 compile errors | ❌ 54 compile errors |
| Curator | ❌ 3 compile errors | ❌ 3 compile errors |
| JacksonCore | ❌ 47 compile errors | ❌ 47 compile errors |
| JacksonAnnotations | ✅ compiles | ✅ compiles |
| Mybatis3 | ✅ compiles | ✅ compiles |
| JSqlParser | ❌ 15938 compile errors | ❌ 15938 compile errors |
| Javaparser | ❌ 1 compile errors | ❌ 1 compile errors |
| Pmd | ❌ 608 compile errors | ❌ 608 compile errors |
| Junit4 | ✅ compiles | ✅ compiles |
| Slf4j | ✅ compiles | ✅ compiles |
| Logback | ❌ 469 compile errors | ❌ 469 compile errors |
| H2database | ✅ compiles | ✅ compiles |
| Dropwizard | ✅ compiles | ✅ compiles |
| Jdbi | ❌ 1 compile errors | ❌ 1 compile errors |
| RestAssured | ✅ compiles | ✅ compiles |
| Pdfbox | ✅ compiles | ✅ compiles |
| Activemq | ❌ 1 compile errors | ❌ 1 compile errors |
| Avro | ✅ compiles | ✅ compiles |
| MavenSurefire | ❌ 57 compile errors | ❌ 57 compile errors |
| HttpcomponentsClient | ✅ compiles | ✅ compiles |
| HttpcomponentsCore | ✅ compiles | ✅ compiles |
| Zookeeper | ⚠️ ecj not used (no compile error) | ⚠️ ecj not used (no compile error) |
| Tika | ⚠️ build failed (no compile error) | ⚠️ build failed (no compile error) |
| VelocityEngine | ✅ compiles | ✅ compiles |
| HibernateValidator | ⚠️ build failed (no compile error) | ⚠️ build failed (no compile error) |
| Checkstyle | ✅ compiles | ✅ compiles |
<!-- status:end -->

### Analysis of the failing projects

| Project | Cause | ECJ issue | Pull request |
|---|---|---|---|
| JDK | generics inference bugs found with this project | [#5583](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5583) to [#5586](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5586) | [#5590](https://github.com/eclipse-jdt/eclipse.jdt.core/pull/5590) (for [#5586](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5586)) |
| Javaparser, Jdbi | a resource directory named like a test class: "The type X collides with a package" | [#4413](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/4413) |  |
| ActiveMQ | `Outer.this.field` read in a lambda: bogus "blank final field may not have been initialized" | [#5593](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5593) |  |
| Curator | anonymous class overriding with the erasure of a type argument: name clash | [#5594](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5594) |  |
| Eclipse Collections | `$deserializeLambda$` exceeds 64 KB with fewer lambdas than javac | [#5595](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5595) | [#5599](https://github.com/eclipse-jdt/eclipse.jdt.core/pull/5599) |
| Guava | a private nested class is not resolved when a static import from a subclass and an enum annotation attribute are combined | [#5596](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5596) |  |
| Guice | method with two generic parameters not applicable to capture variables bounded by a wildcard type | [#5597](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5597) |  |
| Logback, AssertJ, Jackson core, Quarkus, Camel, WildFly, Tika, ZooKeeper, Hibernate Validator, and the other projects with errors | not analysed yet (missing generated sources, module path, annotation processing, or ECJ bugs) |  |  |

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
