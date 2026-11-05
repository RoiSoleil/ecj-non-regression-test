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

The goal is that every project compiles with ECJ without any compile error. The table says, for each project, whether
it compiles today (`❌` lists compile errors of the compiler itself, `⚠️` a build problem that is not a compile error,
for example a plugin that fails before the compilation). Each failing case has to be analysed one by one: a build
configuration problem is fixed in `projects.json` or in the scripts, a real ECJ bug gets an issue.
Regenerate the table with `python3 scripts/readme-status.py results baseline head` after a run.

<!-- status:start -->
| Project | Released ECJ | Head ECJ |
|---|---|---|
| JDK | ⚠️ not run | ⚠️ not run |
| ApacheCommonsIO | ⚠️ not run | ⚠️ not run |
| ApacheCommonsCollections | ⚠️ not run | ⚠️ not run |
| ApacheCommonsLang | ⚠️ not run | ⚠️ not run |
| JacksonDatabind | ⚠️ not run | ⚠️ not run |
| xwiki | ⚠️ not run | ⚠️ not run |
| Eclipse-Collections | ⚠️ not run | ⚠️ not run |
| JavaHamcrest | ⚠️ not run | ⚠️ not run |
| Quarkus | ⚠️ not run | ⚠️ not run |
| Camel | ⚠️ not run | ⚠️ not run |
| WildFly | ⚠️ not run | ⚠️ not run |
| Guava | ⚠️ not run | ⚠️ not run |
| Gson | ⚠️ not run | ⚠️ not run |
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
| Slf4j | ⚠️ not run | ⚠️ not run |
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
| HttpcomponentsCore | ⚠️ not run | ⚠️ not run |
| Zookeeper | ⚠️ not run | ⚠️ not run |
| Tika | ⚠️ not run | ⚠️ not run |
| VelocityEngine | ⚠️ not run | ⚠️ not run |
| HibernateValidator | ⚠️ not run | ⚠️ not run |
| Checkstyle | ⚠️ not run | ⚠️ not run |
| SpringDataCommons | ⚠️ not run | ⚠️ not run |
| SpringDataJpa | ⚠️ not run | ⚠️ not run |
| SpringDataMongodb | ⚠️ not run | ⚠️ not run |
| SpringDataRedis | ⚠️ not run | ⚠️ not run |
| SpringHateoas | ⚠️ not run | ⚠️ not run |
| SpringAi | ⚠️ not run | ⚠️ not run |
| SpringPetclinic | ⚠️ not run | ⚠️ not run |
| Dubbo | ⚠️ not run | ⚠️ not run |
| ShardingSphere | ⚠️ not run | ⚠️ not run |
| Flume | ⚠️ not run | ⚠️ not run |
| OpenNLP | ⚠️ not run | ⚠️ not run |
| Batik | ⚠️ not run | ⚠️ not run |
| Santuario | ⚠️ not run | ⚠️ not run |
| Wss4j | ⚠️ not run | ⚠️ not run |
| Jackrabbit | ⚠️ not run | ⚠️ not run |
| Cayenne | ⚠️ not run | ⚠️ not run |
| Jena | ⚠️ not run | ⚠️ not run |
| Cxf | ⚠️ not run | ⚠️ not run |
| Ignite | ⚠️ not run | ⚠️ not run |
| HBase | ⚠️ not run | ⚠️ not run |
| Hadoop | ⚠️ not run | ⚠️ not run |
| NiFi | ⚠️ not run | ⚠️ not run |
| ShenYu | ⚠️ not run | ⚠️ not run |
| MavenCompilerPlugin | ⚠️ not run | ⚠️ not run |
| MavenShadePlugin | ⚠️ not run | ⚠️ not run |
| MavenDependencyPlugin | ⚠️ not run | ⚠️ not run |
| MavenAssemblyPlugin | ⚠️ not run | ⚠️ not run |
| MavenMvnd | ⚠️ not run | ⚠️ not run |
| CommonsCrypto | ⚠️ not run | ⚠️ not run |
| CommonsDbutils | ⚠️ not run | ✅ compiles |
| CommonsJxpath | ⚠️ not run | ✅ compiles |
| CommonsJcs | ⚠️ not run | ⚠️ not run |
| CommonsRdf | ⚠️ not run | ⚠️ not run |
| MyFaces | ⚠️ not run | ✅ compiles |
| Johnzon | ⚠️ not run | ✅ compiles |
| Jersey | ⚠️ not run | ❌ 713 compile errors |
| Grizzly | ⚠️ not run | ❌ 1702 compile errors |
| Yasson | ⚠️ not run | ❌ 1118 compile errors |
| Mojarra | ⚠️ not run | ✅ compiles |
| Milo | ⚠️ not run | ✅ compiles |
| Tycho | ⚠️ not run | ✅ compiles |
| Truth | ⚠️ not run | ✅ compiles |
| GoogleJavaFormat | ⚠️ not run | ✅ compiles |
| CompileTesting | ⚠️ not run | ✅ compiles |
| Jimfs | ⚠️ not run | ✅ compiles |
| GoogleHttpClient | ⚠️ not run | ✅ compiles |
| JacksonModulesJava8 | ⚠️ not run | ✅ compiles |
| JacksonDataformatsBinary | ⚠️ not run | ❌ 4202 compile errors |
| JacksonDataformatsText | ⚠️ not run | ❌ 2170 compile errors |
| Woodstox | ⚠️ not run | ✅ compiles |
| AaltoXml | ⚠️ not run | ✅ compiles |
| Fastjson2 | ⚠️ not run | ❌ 661 compile errors |
| AlibabaDruid | ⚠️ not run | ✅ compiles |
| Nacos | ⚠️ not run | ✅ compiles |
| Sentinel | ⚠️ not run | ❌ 3 compile errors |
| Canal | ⚠️ not run | ✅ compiles |
| Jedis | ⚠️ not run | ✅ compiles |
| Lettuce | ⚠️ not run | ✅ compiles |
| HikariCP | ⚠️ not run | ⚠️ build failed (no compile error) |
| Liquibase | ⚠️ not run | ❌ 1792 compile errors |
| Immutables | ⚠️ not run | ⚠️ not run |
| ModelMapper | ⚠️ not run | ⚠️ not run |
| Javassist | ⚠️ not run | ✅ compiles |
| EasyMock | ⚠️ not run | ✅ compiles |
| Awaitility | ⚠️ not run | ✅ compiles |
| CucumberJvm | ⚠️ not run | ⚠️ build failed (no compile error) |
| Karate | ⚠️ not run | ✅ compiles |
| Jmh | ⚠️ not run | ⚠️ not run |
| Jol | ⚠️ not run | ✅ compiles |
| Vavr | ⚠️ not run | ❌ 73 compile errors |
| StreamEx | ⚠️ not run | ⚠️ not run |
| Failsafe | ⚠️ not run | ❌ 3 compile errors |
| Bucket4j | ⚠️ not run | ⚠️ build failed (no compile error) |
| AsyncHttpClient | ⚠️ not run | ✅ compiles |
| Jsonschema2pojo | ⚠️ not run | ❌ 678 compile errors |
| JsonSchemaValidator | ⚠️ not run | ⚠️ not run |
| JsonJava | ⚠️ not run | ✅ compiles |
| Kryo | ⚠️ not run | ✅ compiles |
| XStream | ⚠️ not run | ✅ compiles |
| RESTEasy | ⚠️ not run | ❌ 177 compile errors |
| Undertow | ⚠️ not run | ⚠️ not run |
| Thymeleaf | ⚠️ not run | ⚠️ not run |
| HandlebarsJava | ⚠️ not run | ❌ 2704 compile errors |
| Pebble | ⚠️ not run | ⚠️ not run |
| FlexmarkJava | ⚠️ not run | ✅ compiles |
| CommonmarkJava | ⚠️ not run | ⚠️ not run |
| Jjwt | ⚠️ not run | ⚠️ not run |
| Pac4j | ⚠️ not run | ⚠️ not run |
| Ebean | ⚠️ not run | ⚠️ not run |
| Tablesaw | ⚠️ not run | ⚠️ not run |
| Jts | ⚠️ not run | ⚠️ not run |
| JCTools | ⚠️ not run | ⚠️ not run |
| ChronicleQueue | ⚠️ not run | ⚠️ build failed (no compile error) |
| Zip4j | ⚠️ not run | ⚠️ not run |
| JnrFfi | ⚠️ not run | ⚠️ not run |
| ThreeTenExtra | ⚠️ not run | ⚠️ not run |
| JodaMoney | ⚠️ not run | ⚠️ not run |
| JodaBeans | ⚠️ not run | ⚠️ not run |
| Zipkin | ⚠️ not run | ⚠️ not run |
| Brave | ⚠️ not run | ⚠️ not run |
| DropwizardMetrics | ⚠️ not run | ⚠️ not run |
| Oshi | ⚠️ not run | ⚠️ not run |
| JFreeChart | ⚠️ not run | ⚠️ not run |
| HtmlUnit | ⚠️ not run | ⚠️ not run |
| JavaCV | ⚠️ not run | ⚠️ not run |
| JavaCPP | ⚠️ not run | ⚠️ not run |
| ZXing | ⚠️ not run | ⚠️ not run |
| SwaggerParser | ⚠️ not run | ⚠️ not run |
| OpenApiGenerator | ⚠️ not run | ⚠️ not run |
| SpringdocOpenApi | ⚠️ not run | ⚠️ not run |
| Debezium | ⚠️ not run | ⚠️ not run |
| Apollo | ⚠️ not run | ⚠️ not run |
| XxlJob | ⚠️ not run | ⚠️ not run |
| MybatisPageHelper | ⚠️ not run | ⚠️ not run |
| Flowable | ⚠️ not run | ⚠️ not run |
| Jenkins | ⚠️ not run | ⚠️ not run |
| PlexusUtils | ⚠️ not run | ⚠️ not run |
| PlexusCompiler | ⚠️ not run | ⚠️ not run |
| Pf4j | ⚠️ not run | ⚠️ not run |
| SmallRyeConfig | ⚠️ not run | ⚠️ not run |
| SmallRyeMutiny | ⚠️ not run | ⚠️ not run |
| JanusGraph | ⚠️ not run | ⚠️ not run |
| ByteBuddy | ⚠️ not run | ⚠️ not run |
| Spoon | ⚠️ not run | ⚠️ not run |
| Soot | ⚠️ not run | ⚠️ not run |
| Jgrapht | ⚠️ not run | ⚠️ not run |
| Stringtemplate4 | ⚠️ not run | ⚠️ not run |
| Args4j | ⚠️ not run | ⚠️ not run |
| JsonSchema | ⚠️ not run | ⚠️ not run |
| JacksonModulesBase | ⚠️ not run | ❌ 1887 compile errors |
| JacksonDatatypesCollections | ⚠️ not run | ❌ 3093 compile errors |
| JacksonJakartaRsProviders | ⚠️ not run | ✅ compiles |
| JacksonDataformatXml | ⚠️ not run | ⚠️ not run |
| JacksonJr | ⚠️ not run | ✅ compiles |
| JacksonDatatypeJoda | ⚠️ not run | ❌ 328 compile errors |
| Querydsl | ⚠️ not run | ⚠️ ecj not used (no compile error) |
| SqliteJdbc | ⚠️ not run | ❌ 58 compile errors |
| MariadbConnectorJ | ⚠️ not run | ✅ compiles |
| MssqlJdbc | ⚠️ not run | ⚠️ ecj not used (no compile error) |
| Helidon | ⚠️ not run | ❌ 33 compile errors |
| VertxWeb | ⚠️ not run | ❌ 18 compile errors |
| GlassfishHk2 | ⚠️ not run | ❌ 1 compile errors |
| MicroprofileConfig | ⚠️ not run | ⚠️ ecj not used (no compile error) |
| MicroprofileFaultTolerance | ⚠️ not run | ⚠️ ecj not used (no compile error) |
| MicroprofileRestClient | ⚠️ not run | ⚠️ ecj not used (no compile error) |
| SmallryeFaultTolerance | ⚠️ not run | ⚠️ build failed (no compile error) |
| SmallryeOpenApi | ⚠️ not run | ⚠️ not run |
| SmallryeCommon | ⚠️ not run | ⚠️ not run |
| SmallryeJwt | ⚠️ not run | ⚠️ build failed (no compile error) |
| JbossLogging | ⚠️ not run | ✅ compiles |
| JbossModules | ⚠️ not run | ❌ 869 compile errors |
| Xnio | ⚠️ not run | ⚠️ build failed (no compile error) |
| ArquillianCore | ⚠️ not run | ✅ compiles |
| Shrinkwrap | ⚠️ not run | ❌ 126 compile errors |
| SpringBatch | ⚠️ not run | ✅ compiles |
| SpringDataElasticsearch | ⚠️ not run | ✅ compiles |
| SpringDataCassandra | ⚠️ not run | ✅ compiles |
| SpringDataRelational | ⚠️ not run | ✅ compiles |
| SpringDataRest | ⚠️ not run | ✅ compiles |
| SpringDataNeo4j | ⚠️ not run | ⚠️ not run |
| SpringDataCouchbase | ⚠️ not run | ✅ compiles |
| SpringDataLdap | ⚠️ not run | ✅ compiles |
| SpringDataKeyvalue | ⚠️ not run | ⚠️ not run |
| SpringCloudGateway | ⚠️ not run | ⚠️ not run |
| SpringCloudConfig | ⚠️ not run | ✅ compiles |
| SpringCloudOpenfeign | ⚠️ not run | ❌ 1 compile errors |
| SpringCloudCommons | ⚠️ not run | ⚠️ build failed (no compile error) |
| SpringCloudFunction | ⚠️ not run | ✅ compiles |
| SpringCloudNetflix | ⚠️ not run | ✅ compiles |
| SpringCloudAlibaba | ⚠️ not run | ✅ compiles |
| Jetcache | ⚠️ not run | ⚠️ not run |
| SaToken | ⚠️ not run | ✅ compiles |
| IncubatorSeata | ⚠️ not run | ✅ compiles |
| PowerJob | ⚠️ not run | ⚠️ not run |
| MacrozhengMall | ⚠️ not run | ❌ 16 compile errors |
| JavaDesignPatterns | ⚠️ not run | ❌ 2170 compile errors |
| TheAlgorithmsJava | ⚠️ not run | ✅ compiles |
| XmlgraphicsCommons | ⚠️ not run | ✅ compiles |
| QpidJms | ⚠️ not run | ✅ compiles |
| Californium | ⚠️ not run | ✅ compiles |
| DockerJava | ⚠️ not run | ❌ 1 compile errors |
| ItextJava | ⚠️ not run | ❌ 4 compile errors |
| OpenPDF | ⚠️ not run | ❌ 271 compile errors |
| Flyingsaucer | ⚠️ not run | ✅ compiles |
| TwelveMonkeys | ⚠️ not run | ✅ compiles |
| MetadataExtractor | ⚠️ not run | ✅ compiles |
| JavaDiffUtils | ⚠️ not run | ⚠️ not run |
| XChart | ⚠️ not run | ✅ compiles |
| Jte | ⚠️ not run | ✅ compiles |
| Datafaker | ⚠️ not run | ✅ compiles |
| Instancio | ⚠️ not run | ⚠️ not run |
| Xmlunit | ⚠️ not run | ✅ compiles |
| JSONassert | ⚠️ not run | ✅ compiles |
| JsonUnit | ⚠️ not run | ⚠️ not run |
| HdrHistogram | ⚠️ not run | ⚠️ not run |
| Jolokia | ⚠️ not run | ⚠️ not run |
| LogstashLogbackEncoder | ⚠️ not run | ⚠️ not run |
| Rome | ⚠️ not run | ⚠️ not run |
| ChronicleMap | ⚠️ not run | ⚠️ not run |
| ChronicleWire | ⚠️ not run | ⚠️ not run |
| Juneau | ⚠️ not run | ⚠️ not run |
| QpidBrokerJ | ⚠️ not run | ⚠️ not run |
| Helix | ⚠️ not run | ⚠️ not run |
| CommonsScxml | ⚠️ not run | ⚠️ not run |
| Languagetool | ⚠️ not run | ⚠️ not run |
| KubernetesClientJava | ⚠️ not run | ⚠️ not run |
| Jgit | ⚠️ not run | ⚠️ not run |
| Jsch | ⚠️ not run | ⚠️ not run |
| Rdf4j | ⚠️ not run | ⚠️ not run |
| Druid | ⚠️ not run | ⚠️ not run |
| Ditto | ⚠️ not run | ⚠️ not run |
| Graphhopper | ⚠️ not run | ⚠️ not run |
| PrometheusClientJava | ⚠️ not run | ⚠️ not run |
| Activiti | ⚠️ not run | ⚠️ not run |
| Accumulo | ⚠️ not run | ⚠️ not run |
| Phoenix | ⚠️ not run | ⚠️ not run |
| Tez | ⚠️ not run | ⚠️ not run |
| Causeway | ⚠️ not run | ⚠️ not run |
| ServicecombJavaChassis | ⚠️ not run | ⚠️ not run |
| Celeborn | ⚠️ not run | ⚠️ not run |
| CommonsDaemon | ⚠️ not run | ⚠️ not run |
| Ratis | ⚠️ not run | ⚠️ not run |
| Ranger | ⚠️ not run | ⚠️ not run |
| ShardingsphereElasticjob | ⚠️ not run | ⚠️ not run |
| RocketmqSpring | ⚠️ not run | ⚠️ not run |
| MavenJavadocPlugin | ⚠️ not run | ⚠️ not run |
| MavenEnforcer | ⚠️ not run | ⚠️ not run |
| MavenRelease | ⚠️ not run | ⚠️ not run |
| MavenScm | ⚠️ not run | ⚠️ not run |
| MavenWagon | ⚠️ not run | ⚠️ not run |
| MavenArchetype | ⚠️ not run | ⚠️ not run |
| MavenPluginTools | ⚠️ not run | ⚠️ not run |
| MavenIndexer | ⚠️ not run | ⚠️ not run |
| MavenJarPlugin | ⚠️ not run | ⚠️ not run |
| MavenWarPlugin | ⚠️ not run | ⚠️ not run |
| MavenSitePlugin | ⚠️ not run | ⚠️ not run |
| MavenInvokerPlugin | ⚠️ not run | ⚠️ not run |
| MavenHelpPlugin | ⚠️ not run | ⚠️ not run |
| MavenSharedUtils | ⚠️ not run | ⚠️ not run |
| MavenFiltering | ⚠️ not run | ⚠️ not run |
| MavenResourcesPlugin | ⚠️ not run | ⚠️ not run |
| MavenPmdPlugin | ⚠️ not run | ⚠️ not run |
| MavenCheckstylePlugin | ⚠️ not run | ⚠️ not run |
| MavenEarPlugin | ⚠️ not run | ⚠️ not run |
| MavenSourcePlugin | ⚠️ not run | ⚠️ not run |
| MavenInstallPlugin | ⚠️ not run | ⚠️ not run |
| MavenDeployPlugin | ⚠️ not run | ⚠️ not run |
| MavenCleanPlugin | ⚠️ not run | ⚠️ not run |
| MavenGpgPlugin | ⚠️ not run | ⚠️ not run |
| MavenAntrunPlugin | ⚠️ not run | ⚠️ not run |
| MavenProjectInfoReportsPlugin | ⚠️ not run | ⚠️ not run |
| MavenDoxia | ⚠️ not run | ⚠️ not run |
| MavenDoxiaSitetools | ⚠️ not run | ⚠️ not run |
| MavenDependencyTree | ⚠️ not run | ⚠️ not run |
| MavenArchiver | ⚠️ not run | ⚠️ not run |
| MavenJlinkPlugin | ⚠️ not run | ⚠️ not run |
| MavenBuildCacheExtension | ⚠️ not run | ⚠️ not run |
| Soteria | ⚠️ not run | ⚠️ not run |
| Exousia | ⚠️ not run | ⚠️ not run |
| Expressly | ⚠️ not run | ⚠️ not run |
| GlassfishConcurro | ⚠️ not run | ⚠️ not run |
| JakartaServlet | ⚠️ not run | ⚠️ not run |
| JakartaCdi | ⚠️ not run | ⚠️ not run |
| JakartaRest | ⚠️ not run | ⚠️ not run |
| JakartaPersistence | ⚠️ not run | ⚠️ not run |
| JsonbApi | ⚠️ not run | ⚠️ not run |
| JakartaWebsocket | ⚠️ not run | ⚠️ not run |
| JakartaMessaging | ⚠️ not run | ⚠️ not run |
| JakartaExpressionLanguage | ⚠️ not run | ⚠️ not run |
| JakartaAuthentication | ⚠️ not run | ⚠️ not run |
| JakartaInterceptors | ⚠️ not run | ⚠️ not run |
| JakartaInject | ⚠️ not run | ⚠️ not run |
| MicroprofileHealth | ⚠️ not run | ⚠️ not run |
| MicroprofileMetrics | ⚠️ not run | ⚠️ not run |
| MicroprofileOpenApi | ⚠️ not run | ⚠️ not run |
| MicroprofileJwtAuth | ⚠️ not run | ⚠️ not run |
| MicroprofileReactiveMessaging | ⚠️ not run | ⚠️ not run |
| MicroprofileGraphql | ⚠️ not run | ⚠️ not run |
| MicroprofileLra | ⚠️ not run | ⚠️ not run |
| MicroprofileContextPropagation | ⚠️ not run | ⚠️ not run |
| EclipseStore | ⚠️ not run | ⚠️ not run |
| EclipseSerializer | ⚠️ not run | ⚠️ not run |
| Jnosql | ⚠️ not run | ⚠️ not run |
| VertxSqlClient | ⚠️ not run | ⚠️ not run |
| VertxAuth | ⚠️ not run | ⚠️ not run |
| Lemminx | ⚠️ not run | ⚠️ not run |
| WildflyElytron | ⚠️ not run | ⚠️ not run |
| JbossRemoting | ⚠️ not run | ⚠️ not run |
| JbossLogmanager | ⚠️ not run | ⚠️ not run |
| JbossThreads | ⚠️ not run | ⚠️ not run |
| Jandex | ⚠️ not run | ⚠️ not run |
| SmallryeContextPropagation | ⚠️ not run | ⚠️ not run |
| SmallryeOpentelemetry | ⚠️ not run | ⚠️ not run |
| SmallryeStork | ⚠️ not run | ⚠️ not run |
| HibernateTools | ⚠️ not run | ⚠️ not run |
| SpringPlugin | ⚠️ not run | ⚠️ not run |
| SpringVault | ⚠️ not run | ⚠️ not run |
| SpringModulith | ⚠️ not run | ⚠️ not run |
| SpringCloudStream | ⚠️ not run | ⚠️ not run |
| SpringCloudKubernetes | ⚠️ not run | ⚠️ not run |
| SpringCloudBus | ⚠️ not run | ⚠️ not run |
| SpringCloudConsul | ⚠️ not run | ⚠️ not run |
| SpringCloudZookeeper | ⚠️ not run | ⚠️ not run |
| SpringCloudVault | ⚠️ not run | ⚠️ not run |
| SpringCloudCircuitbreaker | ⚠️ not run | ⚠️ not run |
| SpringCloudTask | ⚠️ not run | ⚠️ not run |
| SpringBootAdmin | ⚠️ not run | ⚠️ not run |
| QLExpress | ⚠️ not run | ⚠️ not run |
| Eladmin | ⚠️ not run | ⚠️ not run |
| RuoyiVuePro | ⚠️ not run | ⚠️ not run |
| RuoYi | ⚠️ not run | ⚠️ not run |
| Litemall | ⚠️ not run | ⚠️ not run |
| NewbeeMall | ⚠️ not run | ⚠️ not run |
| PigMesh | ⚠️ not run | ⚠️ not run |
| ChaosbladeExecJvm | ⚠️ not run | ⚠️ not run |
| JsonldJava | ⚠️ not run | ⚠️ not run |
| SwaggerCodegen | ⚠️ not run | ⚠️ not run |
| JavaHtmlSanitizer | ⚠️ not run | ⚠️ not run |
| EsapiJavaLegacy | ⚠️ not run | ⚠️ not run |
| FindSecBugs | ⚠️ not run | ⚠️ not run |
| ApprovalTestsJava | ⚠️ not run | ⚠️ not run |
| JunitQuickcheck | ⚠️ not run | ⚠️ not run |
| Zerocode | ⚠️ not run | ⚠️ not run |
| SparkJava | ⚠️ not run | ⚠️ not run |
| Jooby | ⚠️ not run | ⚠️ not run |
| VaadinFlow | ⚠️ not run | ⚠️ not run |
| Omnifaces | ⚠️ not run | ⚠️ not run |
| Jfinal | ⚠️ not run | ⚠️ not run |
| MybatisSpring | ⚠️ not run | ⚠️ not run |
| MybatisDynamicSql | ⚠️ not run | ⚠️ not run |
| SpringBootStarter | ⚠️ not run | ⚠️ not run |
| HypersistenceUtils | ⚠️ not run | ⚠️ not run |
| Neo4jJavaDriver | ⚠️ not run | ⚠️ not run |
| InfluxdbClientJava | ⚠️ not run | ⚠️ not run |
| Logbook | ⚠️ not run | ⚠️ not run |
| Orika | ⚠️ not run | ⚠️ not run |
| JavaThreadAffinity | ⚠️ not run | ⚠️ not run |
| ChronicleCore | ⚠️ not run | ⚠️ not run |
| ChronicleBytes | ⚠️ not run | ⚠️ not run |
| ZeroAllocationHashing | ⚠️ not run | ⚠️ not run |
| Aircompressor | ⚠️ not run | ⚠️ not run |
| Slice | ⚠️ not run | ⚠️ not run |
| Airline | ⚠️ not run | ⚠️ not run |
| CoreNLP | ⚠️ not run | ⚠️ not run |
| JiebaAnalysis | ⚠️ not run | ⚠️ not run |
| Docx4j | ⚠️ not run | ⚠️ not run |
| Openhtmltopdf | ⚠️ not run | ⚠️ not run |
| ExecMavenPlugin | ⚠️ not run | ⚠️ not run |
| Versions | ⚠️ not run | ⚠️ not run |
| BuildHelperMavenPlugin | ⚠️ not run | ⚠️ not run |
| Jaxb2MavenPlugin | ⚠️ not run | ⚠️ not run |
| LicenseMavenPlugin | ⚠️ not run | ⚠️ not run |
| FlattenMavenPlugin | ⚠️ not run | ⚠️ not run |
| AnimalSniffer | ⚠️ not run | ⚠️ not run |
| PlexusArchiver | ⚠️ not run | ⚠️ not run |
| PlexusClassworlds | ⚠️ not run | ⚠️ not run |
| PlexusInterpolation | ⚠️ not run | ⚠️ not run |
| SisuProject | ⚠️ not run | ⚠️ not run |
| FormatterMavenPlugin | ⚠️ not run | ⚠️ not run |
| DockerMavenPlugin | ⚠️ not run | ⚠️ not run |
| FrontendMavenPlugin | ⚠️ not run | ⚠️ not run |
| Clojure | ⚠️ not run | ⚠️ not run |
| Mvel | ⚠️ not run | ⚠️ not run |
| Ognl | ⚠️ not run | ⚠️ not run |
| Hipparchus | ⚠️ not run | ⚠️ not run |
| Tribuo | ⚠️ not run | ⚠️ not run |
| GsCore | ⚠️ not run | ⚠️ not run |
| Cdk | ⚠️ not run | ⚠️ not run |
| Biojava | ⚠️ not run | ⚠️ not run |
| Geotools | ⚠️ not run | ⚠️ not run |
| Spatial4j | ⚠️ not run | ⚠️ not run |
| JGroups | ⚠️ not run | ⚠️ not run |
| DbScheduler | ⚠️ not run | ⚠️ not run |
| ShedLock | ⚠️ not run | ⚠️ not run |
| DSpace | ⚠️ not run | ⚠️ not run |
| OpenRefine | ⚠️ not run | ⚠️ not run |
| JitsiVideobridge | ⚠️ not run | ⚠️ not run |
| Jicofo | ⚠️ not run | ⚠️ not run |
| Openfire | ⚠️ not run | ⚠️ not run |
| OpenTripPlanner | ⚠️ not run | ⚠️ not run |
| SignalServer | ⚠️ not run | ⚠️ not run |
| JacksonDatabindNullable | ⚠️ not run | ⚠️ not run |
| JavaClassmate | ⚠️ not run | ⚠️ not run |
| JacksonDatatypeHibernate | ⚠️ not run | ⚠️ not run |
| JacksonModuleJsonSchema | ⚠️ not run | ⚠️ not run |
| JaxbApi | ⚠️ not run | ⚠️ not run |
| SpringPetclinicMicroservices | ⚠️ not run | ⚠️ not run |
| SpringPetclinicRest | ⚠️ not run | ⚠️ not run |
| SpringFrameworkPetclinic | ⚠️ not run | ⚠️ not run |
| VelocityScripting | ⚠️ not run | ⚠️ not run |
| FreemarkerScripting | ⚠️ not run | ⚠️ not run |
| ThymeleafScripting | ⚠️ not run | ⚠️ not run |
| EhcacheCache | ⚠️ not run | ⚠️ not run |
| RedisCache | ⚠️ not run | ⚠️ not run |
| AssertjDb | ⚠️ not run | ⚠️ not run |
| Expiringmap | ⚠️ not run | ⚠️ not run |
| Classgraph | ⚠️ not run | ⚠️ not run |
| Reflections | ⚠️ not run | ⚠️ not run |
| JnrUnixsocket | ⚠️ not run | ⚠️ not run |
| JnrConstants | ⚠️ not run | ⚠️ not run |
| EoYaml | ⚠️ not run | ⚠️ not run |
| UnirestJava | ⚠️ not run | ⚠️ not run |
| FusionauthJwt | ⚠️ not run | ⚠️ not run |
| Cache2k | ⚠️ not run | ⚠️ not run |
| Disruptor | ⚠️ not run | ⚠️ not run |
| AvajeJsonb | ⚠️ not run | ⚠️ not run |
| AvajeValidator | ⚠️ not run | ⚠️ not run |
| Nutz | ⚠️ not run | ⚠️ not run |
| SpringCloudTencent | ⚠️ not run | ⚠️ not run |
| Discovery | ⚠️ not run | ⚠️ not run |
| MallSwarm | ⚠️ not run | ⚠️ not run |
| Streampipes | ⚠️ not run | ⚠️ not run |
| Systemds | ⚠️ not run | ⚠️ not run |
| JackrabbitFilevault | ⚠️ not run | ⚠️ not run |
| Kapua | ⚠️ not run | ⚠️ not run |
| Hawkbit | ⚠️ not run | ⚠️ not run |
| Jkube | ⚠️ not run | ⚠️ not run |
| Revapi | ⚠️ not run | ⚠️ not run |
| Moditect | ⚠️ not run | ⚠️ not run |
| CommonsOgnl | ⚠️ not run | ⚠️ not run |
| MavenResolverAntTasks | ⚠️ not run | ⚠️ not run |
| CreadurRat | ⚠️ not run | ⚠️ not run |
| Cargotracker | ⚠️ not run | ⚠️ not run |
| Starter | ⚠️ not run | ⚠️ not run |
| QuarkusQuickstarts | ⚠️ not run | ⚠️ not run |
| HelidonExamples | ⚠️ not run | ⚠️ not run |
| SpringDataExamples | ⚠️ not run | ⚠️ not run |
| GraphqlJavaTools | ⚠️ not run | ⚠️ not run |
| Jeromq | ⚠️ not run | ⚠️ not run |
| RabbitmqStreamJavaClient | ✅ compiles | ✅ compiles |
| CiMaven | ❌ 2 compile errors | ❌ 2 compile errors |
| WildflyMavenPlugin | ✅ compiles | ✅ compiles |
| JbossParentPom | ⚠️ ecj not used (no compile error) | ⚠️ not run |
<!-- status:end -->

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
