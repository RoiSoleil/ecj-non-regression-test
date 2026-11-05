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
| 122 more Maven projects: Spring Data, Spring AI, Dubbo, HBase, Hadoop, Ignite, NiFi, ShardingSphere, Jena, CXF, Jenkins, Debezium, Liquibase, Nacos, Sentinel, Apollo, Jedis, Lettuce, HikariCP, Vavr, Truth, google-java-format, JMH, Undertow, Thymeleaf, ZXing, JTS... | Maven (see `projects.json`) |
| Eclipse Collections | Maven (`install`) |
| JavaHamcrest | Gradle (ECJ Gradle plugin, see `patches/`) |
| Quarkus, Camel, WildFly | Maven (`install`, several hours: the baseline and the head ECJ run in two parallel jobs) |

Every project is pinned to a commit (`projects.json`), so the known errors stay the same from one run to the next.
Update the pins in a pull request.

## Performance: javac against ECJ

Every project is also built untouched with the JDK's `javac` (label `javac`, no ECJ, no patch). The javac and head runs
build each project twice: the first build downloads the dependencies and is not measured. Then the compiled classes are
deleted and the project is built again offline (`mvn -o`) with `-Xms4g -Xmx4g -XX:+UseG1GC`: three times when the first
build took under 2 minutes (the median is reported, the minimum and maximum are kept), once otherwise.
A warm-up build that fails on a network error (a 502 from Maven Central, a timeout) is tried again, up to 3 times.
The baseline run has no warm-up build (it only gives the reference compile errors).

Metrics (`scripts/metrics.py`): wall and CPU time, compile time (the time spent in the compiler plugin, from the time
stamps of the Maven log), peak memory, garbage collections (`-Xlog:gc,gc+cpu`: pauses, CPU time of the GC threads,
allocated memory) and the class files produced (the number says whether both compilers did the same work).
`python3 scripts/perf-compare.py results javac head` prints, for every project that builds with both compilers, the
figures and the fastest compiler (compile time when measured, a difference under 5 % is a tie); with `--html report.html`
it also writes a standalone report with a chart (the workflow uploads it as the `performance-report` artifact).
The Java Flight Recording (head run, about 1 % overhead) keeps the last measured build. Allocated memory is approximate (heap occupancy between collections). Failing builds are not compared. Shared CI runners are noisy: read the table as a trend.

## Status

[![ECJ Non-regression Builds](https://github.com/RoiSoleil/ecj-non-regression-test/actions/workflows/ecj-matrix.yml/badge.svg)](https://github.com/RoiSoleil/ecj-non-regression-test/actions/workflows/ecj-matrix.yml)
[![Dashboard](https://img.shields.io/badge/dashboard-GitHub%20Pages-2f6fde)](https://roisoleil.github.io/ecj-non-regression-test/)

The goal is that every project compiles with ECJ without any compile error. The
[dashboard](https://roisoleil.github.io/ecj-non-regression-test/) shows, for each run, whether each project compiles
with the released ECJ, the head ECJ and javac, its compile errors grouped by families, and the performance of the
compilers (time, CPU, memory, GC), with the history of the last 60 runs and a page per project. Every number links to
the raw file it comes from. Each failing case has to be analysed one by one: a build configuration problem is fixed in
`projects.json` or in the scripts, a real ECJ bug gets an issue.

### Analysis of the failing projects

| Project | Cause | ECJ issue | Pull request |
|---|---|---|---|
| JDK | generics inference: `MethodHandles` ([#5583](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5583)) and `ClassRemapperImpl` ([#5584](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5584)). [#5585](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5585) and [#5586](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5586) come from the JustJ 25.0.4 sources of every module | [#5583](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5583) to [#5586](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5586) | [#5590](https://github.com/eclipse-jdt/eclipse.jdt.core/pull/5590) (merged, for [#5586](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5586)) |
| Javaparser, Jdbi | a resource directory named like a test class: "The type X collides with a package" | [#4413](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/4413) | [#5628](https://github.com/eclipse-jdt/eclipse.jdt.core/pull/5628) |
| ActiveMQ | `Outer.this.field` read in a lambda: bogus "blank final field may not have been initialized" | [#5593](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5593) | [#5645](https://github.com/eclipse-jdt/eclipse.jdt.core/pull/5645) |
| Curator | anonymous class overriding with the erasure of a type argument: name clash | [#5594](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5594) |  |
| Eclipse Collections | `$deserializeLambda$` exceeds 64 KB with fewer lambdas than javac | [#5595](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5595) | [#5599](https://github.com/eclipse-jdt/eclipse.jdt.core/pull/5599) |
| Guava | 10 errors: a private nested class is not resolved when a static import from a subclass and an enum annotation attribute are combined. 1 error: `Futures.whenAllComplete(ImmutableList<FluentFuture<?>>)` "not applicable" in `ClosingFuture`, independent of [#5596](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5596) (javac accepts it, not reduced yet) | [#5596](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5596) |  |
| Guice | method with two generic parameters not applicable to capture variables bounded by a wildcard type | [#5597](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5597) |  |
| AssertJ, JSqlParser, Quarkus (tests of qute core, arc runtime, classloader commons), Jetty (tests of quic-util, slf4j-impl), Apache Maven (tests of maven-api-settings) | tests of a modular project: ECJ's javax.tools compiler ignores `--patch-module` (`EclipseCompilerImpl.setPaths` does not call `handlePatchModule`), so the tests compile in the unnamed module: "The package X is accessible from more than one module: <unnamed>, X". The batch compiler applies it but writes no class file | not reported yet |  |
| Jackson core | its test `module-info.java` requires `org.assertj.core`, a multi-release jar whose only module descriptor is `META-INF/versions/9/module-info.class`: ECJ reads it only with `--release` | [#2774](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/2774) |  |
| jsoup | `src/main/java11` with its `module-info.java`, patched into the classes compiled before: ECJ does not support `--patch-module` with a class directory | not reported yet |  |
| Apache Maven (maven-xml) | its own `target/classes` is on the module path: ECJ makes an automatic module of a directory that only holds `META-INF/services` files | not reported yet |  |
| Apache Maven (maven-api-di), Quarkus (data processor) | annotation processors run although `<proc>none</proc>`: plexus-compiler-eclipse does not pass `-proc:none` ([plexus #528](https://github.com/codehaus-plexus/plexus-compiler/issues/528)); Quarkus not checked |  | [plexus #529](https://github.com/codehaus-plexus/plexus-compiler/pull/529) |
| PMD | 602 errors from this repository: a pom packaging got a compiler plugin (fixed in `enable-ecj-maven.py`, to be confirmed by a run). 6 errors in pmd-java and pmd-apex on the self-typed node API (`getLastChild()`, `ancestors().get(1)`, `descendants()`): probable ECJ bugs, not reduced yet |  |  |
| Camel | this repository: the rewritten poms lost their comments, which camel-package-maven-plugin reads (fixed in `enable-ecj-maven.py`, to be confirmed by a run) |  |  |
| WildFly | the JBoss Logging processor calls `Filer.getResource(CLASS_OUTPUT, ...)` for a file that does not exist: ECJ throws `FileNotFoundException` (the `Filer` specification allows it), javac returns a file object. Worked around with `ecj_compiler_args` (`-AtranslationFilesPath`) |  |  |
| Shiro | Lombok (`@RequiredArgsConstructor`, `@Delegate`) in the tests: Lombok works with ECJ only through its Java agent |  |  |
| Netty | `MethodHandle.invoke` and `invokeExact` (signature polymorphic) "undefined" in netty-common, compiled forked with `release 8`: not reproduced outside the build yet |  |  |
| Tika | `IllegalArgumentException` without a message in the test compilation of tika-pipes-config-store-ignite (pf4j annotation processor): not reproduced yet |  |  |
| ZooKeeper | the ECJ builds do not run the `javacc` and `pre-compile-jute` executions of zookeeper-jute, so the Jute compiler (`Rcc`) is missing: cause not found yet |  |  |
| Gson, Maven Surefire, Hibernate Validator | build configuration, javac fails the same way (Gson: `test-jpms` needs the packaged module; Surefire: the shaded `surefire-shared-utils`; Hibernate Validator: a zip of the reactor that is not built yet) |  |  |

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
5. `scripts/dashboard-data.py` turns the results of the run into the JSON files of the dashboard, and
   `scripts/publish-dashboard.sh` publishes them with the site (`dashboard/`) on the `gh-pages` branch: summaries of
   the last 60 runs, raw files (`.status`, `.metrics`, `.errors`, build logs) of the last 10.

The workflow `ECJ Non-regression Builds` (`.github/workflows/ecj-matrix.yml`) runs three jobs per project (baseline ECJ, head ECJ and javac, in parallel) and a final `compare` job. A matrix cannot generate more than 256 jobs, so the projects are split in shards of 100, one call of `ecj-build.yml` per shard and label: adding projects only takes `projects.json`. The
`ECJ Commit Watcher` workflow (`ecj-check.yml`) runs it every night when `eclipse.jdt.core` has a new commit; a
successfully tested commit gets a `tested/<sha>` tag, a failing run is retried the next night.

## Run it

*Actions > ECJ Non-regression Builds > Run workflow*

* `ecj_ref`: branch, tag or commit of `eclipse.jdt.core` (a pull request head works: `refs/pull/<n>/head`).
  Default: `master`.
* `baseline`: released ECJ version to compare with (default: the latest release on Maven Central).
* `projects`: comma separated names, for example `Quarkus,Camel`. Default: all projects.
* `jfr`: `true` (default) records a [Java Flight Recording](https://dev.java/learn/jvm/jfr/) of each build with the head ECJ.

Each head job uploads its recording as the artifact `jfr-<project>` (kept 14 days, at most 300 MB per project,
`profile` settings raised to the maximum: CPU sample every 5 ms, 1000 allocation samples per second, stacks of 2048 frames,
1 ms thresholds for I/O, locks and JIT, old object samples; see `scripts/run-project.sh` and its `JFR_*` environment
variables; the overhead has not been measured yet, expect a few %). Download it from the run page and open it with JDK Mission Control or
`jfr print --events jdk.ExecutionSample <file>.jfr`. ECJ runs inside the Maven JVM (and inside the `java` process of the
JDK project); the Gradle project (JavaHamcrest) is not recorded.

The summary of each job shows the table of the run and, for each project, the new and the vanished errors.

Locally (JDK 27, or the JDK of the `jdk` field of the project, Maven 3.9.9 or later, `jq`):

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

* The projects are built with JDK 27, or the JDK of their `jdk` field in `projects.json`: the JDK project compiles the
  sources of JDK 25, since the baseline ECJ supports Java 26 at most.
* A new project is added only if it builds with `javac` on this setup (no network service, no native toolchain).
  Tried and not kept yet: needing `install` instead of `compile` (`has not been packaged yet`): Karaf, MINA SSHD,
  OpenJPA, TomEE, Maven Resolver, OpenWebBeans, MapStruct; other build problems with javac: see the history of
  `projects.json`.
* 48 projects build with javac on JDK 21 only (`"jdk": "21"`). 136 candidates added on 2026-11-02 and 03 did not build with javac
  on JDK 21 nor 27 and were removed (list in the history of `projects.json`).
* With JDK 27, ECJ fails on projects that it compiles on JDK 21: APIs removed after the release of the project
  ([#5660](https://github.com/eclipse-jdt/eclipse.jdt.core/issues/5660): javax.tools ignores `--release`, fixed by
  [#5663](https://github.com/eclipse-jdt/eclipse.jdt.core/pull/5663)), and module errors ("The package ... conflicts with a
  package accessible from another module", "... cannot be resolved to a module") not analysed yet.
* Joda-Time is not tested: its sources are Java 1.5, which a current ECJ no longer accepts.

* Only the root `pom.xml` is switched to ECJ. A module that sets its own `compilerId` (or a profile-scoped compiler
  plugin) still compiles with javac; the run only checks that at least one module reported `Compiling with eclipse`.
* Gradle projects (JavaHamcrest) are not checked for ECJ use.
* Errors are compared as `path:line message`; a reworded diagnostic shows as one new and one vanished error.
* A project that already fails with the baseline ECJ (Eclipse Collections: `$deserializeLambda$` exceeds 64 KB) only
  detects new compile error lines, not new crashes.
* The head ECJ is built from the batch compiler sources only, with a fake version `3.99.0`. The annotation processing
  classes are compiled with JDK 25 and run on the JDK of the build.

This repository was written with the help of Claude (AI).
