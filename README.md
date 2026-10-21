# ECJ non-regression test

Builds real projects with the latest `eclipse.jdt.core` compiler (ECJ) and with the last released ECJ, and reports
the compile errors that only the new compiler gives.

* `projects.json`: the projects (repository, pinned revision, build command). Projects marked `optional` (Quarkus,
  Camel, WildFly) are only built when named in the `projects` input.
* `scripts/build-ecj.sh`: builds the ECJ batch compiler of an `eclipse.jdt.core` checkout with javac (a few seconds).
* `scripts/enable-ecj-maven.py`: makes a Maven build compile with ECJ (`plexus-compiler-eclipse`). Gradle projects
  use a patch from `patches/`.
* `scripts/run-project.sh`: builds one project and records status and compile errors.
* `scripts/compare.py`: baseline against head; fails when the head ECJ has errors the baseline does not, or does not
  build a project the baseline builds.

Run by hand: *Actions > ECJ Non-regression Builds > Run workflow* (`ecj_ref` can be a branch or a commit of a pull
request). The watcher workflow runs every night when `eclipse.jdt.core` has a new commit.

The pinned revisions keep the known errors stable; update them in a pull request.

This repository was written with the help of Claude (AI).
