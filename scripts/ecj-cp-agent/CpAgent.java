import java.io.File;
import java.lang.instrument.Instrumentation;
import java.util.jar.JarFile;

public class CpAgent {
    public static void premain(String args, Instrumentation instrumentation) throws Exception {
        for (String path : args.split(File.pathSeparator)) {
            instrumentation.appendToSystemClassLoaderSearch(new JarFile(path));
        }
    }
}
