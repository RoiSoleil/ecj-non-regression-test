val merapiJavac: String? = System.getenv("MERAPI_JAVAC")
if (!merapiJavac.isNullOrEmpty()) {
    val merapiHome = File(merapiJavac).parentFile.parentFile.canonicalFile
    allprojects {
        tasks.withType<JavaCompile>().configureEach {
            val compile = this
            options.isFork = true
            options.forkOptions.executable = merapiJavac
            doFirst {
                val home = compile.javaCompiler.orNull?.metadata?.installationPath?.asFile?.canonicalFile
                if (home != null && home != merapiHome) {
                    compile.options.forkOptions.executable = null
                    compile.logger.lifecycle("merapi skipped ${compile.path}: its toolchain is $home")
                }
            }
        }
    }
}
