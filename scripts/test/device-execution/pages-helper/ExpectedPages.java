import com.ohos.hapsigntool.zip.Zip;
import com.ohos.hapsigntool.codesigning.sign.PageInfoGenerator;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.zip.ZipFile;

/** 仅从批准 unsigned 快照派生官方 bitmap；不调用任何签名或私钥 API。 */
public final class ExpectedPages {
    static final String JAR_SHA256 = "a434b6747e6c5d0b14e73837a46b39f4816ab25b42d1833d6f767bf867cf616d";
    static final int MAX_HAP = 128 * 1024 * 1024;
    static void require(boolean value) {
        if (!value) throw new IllegalArgumentException("pages-contract");
    }
    static String sha(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    static byte[] regularBytes(Path path) throws Exception {
        BasicFileAttributes info = Files.readAttributes(path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        require(info.isRegularFile() && info.size() > 0 && info.size() <= MAX_HAP);
        try (InputStream input = Files.newInputStream(path, LinkOption.NOFOLLOW_LINKS)) {
            byte[] bytes = input.readNBytes(MAX_HAP + 1);
            require(bytes.length == info.size() && bytes.length <= MAX_HAP);
            return bytes;
        }
    }
    static void validateMembers(Path input) throws Exception {
        HashSet<String> names = new HashSet<>();
        try (ZipFile zip = new ZipFile(input.toFile())) {
            var entries = zip.entries();
            int count = 0;
            while (entries.hasMoreElements()) {
                var entry = entries.nextElement();
                String name = entry.getName();
                require(++count <= 4096 && !name.isEmpty() && name.length() <= 4096);
                require(!name.startsWith("/") && !name.contains("\\") && !name.contains(":"));
                require(name.chars().noneMatch(c -> c < 32 || c == 127));
                String canonical = name.endsWith("/") ? name.substring(0, name.length()-1) : name;
                require(!canonical.isEmpty());
                for (String part : canonical.split("/", -1))
                    require(!part.isEmpty() && !part.equals(".") && !part.equals(".."));
                require(!canonical.equals(".pages.info") && names.add(canonical));
            }
            require(count > 0);
        }
    }
    static String derive(Path input, String expected, Path output) throws Exception {
        require(expected.matches("[0-9a-f]{64}"));
        Path jar = Path.of(Zip.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        Path generatorJar = Path.of(PageInfoGenerator.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        require(jar.equals(generatorJar) && sha(regularBytes(jar)).equals(JAR_SHA256));
        byte[] bytes = regularBytes(input);
        require(sha(bytes).equals(expected));
        require(!Files.exists(output, LinkOption.NOFOLLOW_LINKS));
        Path dir = Files.createTempDirectory(input.toAbsolutePath().getParent(), ".vidall-pages-",
            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")));
        Path snapshot = dir.resolve("unsigned.hap");
        boolean outputCreated = false;
        boolean complete = false;
        try {
            Files.createFile(snapshot, PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
            Files.write(snapshot, bytes);
            validateMembers(snapshot);
            Zip zip = new Zip(snapshot.toFile());
            zip.alignment(4);
            byte[] pages = new PageInfoGenerator(zip).generateBitMap();
            require(pages != null && pages.length > 0 && pages.length <= 1024 * 1024);
            String digest = sha(pages);
            // CREATE_NEW 防止覆盖任何既有输出；权限在创建时即为 0600。
            Files.createFile(output, PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
            outputCreated = true;
            Files.write(output, pages);
            require(sha(regularBytes(output)).equals(digest));
            String result = "{\"schemaVersion\":1,\"derived\":true,\"unsignedHAP_SHA256\":\"" + expected
                + "\",\"alignment\":4,\"signCode\":1,\"pagesSHA256\":\"" + digest + "\",\"pagesBytes\":" + pages.length + "}";
            complete = true;
            return result;
        } finally {
            Files.deleteIfExists(snapshot);
            Files.deleteIfExists(dir);
            if (outputCreated && !complete) Files.deleteIfExists(output);
        }
    }
    public static void main(String[] args) {
        PrintStream response = System.out;
        System.setOut(new PrintStream(OutputStream.nullOutputStream()));
        System.setErr(new PrintStream(OutputStream.nullOutputStream()));
        try {
            require(args.length == 3);
            response.println(derive(Path.of(args[0]), args[1], Path.of(args[2])));
        } catch (Exception | LinkageError failure) {
            response.println("{\"schemaVersion\":1,\"derived\":false}");
            System.exit(1);
        }
    }
}
