import com.ohos.hapsigntool.hap.verify.VerifyHap;
import com.ohos.hapsigntool.hap.verify.VerifyResult;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.MessageDigest;
import java.util.Collection;
import java.util.Date;
import java.util.HexFormat;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cms.SignerInformation;

/** 同锁定官方 JAR 验签，再以真实 CMS SignerInfo SID 唯一选择应用证书。 */
public final class ActualSigner {
    static final String JAR_SHA256 = "a434b6747e6c5d0b14e73837a46b39f4816ab25b42d1833d6f767bf867cf616d";
    static final int MAX_HAP = 128 * 1024 * 1024;
    static void require(boolean value) {
        if (!value) throw new IllegalArgumentException("signer-contract");
    }
    static boolean hashFormat(String value) {
        return value != null && value.matches("[0-9a-f]{64}");
    }
    static String sha(byte[] value) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
    }
    @SuppressWarnings({"unchecked", "rawtypes"})
    static String selectSigner(VerifyResult result, String expected) throws Exception {
        require(hashFormat(expected) && result != null && result.isVerified());
        require(result.getSignerInfos() != null && result.getSignerInfos().size() == 1);
        require(result.getCertificateHolderStore() != null);
        SignerInformation signer = result.getSignerInfos().get(0);
        require(signer != null && signer.getSID() != null);
        Collection<X509CertificateHolder> matches = result.getCertificateHolderStore()
            .getMatches(signer.getSID());
        require(matches != null && matches.size() == 1);
        X509CertificateHolder certificate = matches.iterator().next();
        Date now = new Date();
        require(!now.before(certificate.getNotBefore()) && !now.after(certificate.getNotAfter()));
        String actual = sha(certificate.getEncoded());
        require(actual.equals(expected));
        return actual;
    }
    static byte[] regularBytes(Path path, int limit) throws Exception {
        BasicFileAttributes info = Files.readAttributes(path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        require(info.isRegularFile() && info.size() > 0 && info.size() <= limit);
        try (InputStream input = Files.newInputStream(path, LinkOption.NOFOLLOW_LINKS)) {
            byte[] data = input.readNBytes(limit + 1);
            require(data.length == info.size() && data.length <= limit);
            return data;
        }
    }
    static String verify(Path input, String expectedHap, String expectedSigner) throws Exception {
        require(hashFormat(expectedHap) && hashFormat(expectedSigner));
        Path jar = Path.of(VerifyHap.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        require(sha(regularBytes(jar, MAX_HAP)).equals(JAR_SHA256));
        byte[] bytes = regularBytes(input, MAX_HAP);
        require(sha(bytes).equals(expectedHap));
        // 官方工具读取本次私有快照；原路径在校验中被替换也不改变被验字节。
        Path directory = Files.createTempDirectory(input.toAbsolutePath().getParent(), ".vidall-signer-",
            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")));
        Path snapshot = directory.resolve("signed.hap");
        try {
            Files.createFile(snapshot,
                PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
            Files.write(snapshot, bytes);
            VerifyResult result = new VerifyHap().verifyHap(snapshot.toString());
            require(sha(regularBytes(snapshot, MAX_HAP)).equals(expectedHap));
            return selectSigner(result, expectedSigner);
        } finally {
            Files.deleteIfExists(snapshot);
            Files.delete(directory);
        }
    }
    public static void main(String[] args) {
        PrintStream stdout = System.out;
        PrintStream stderr = System.err;
        boolean verified = false;
        String hap = "", signer = "";
        // 官方库日志可能含路径/证书；只发布最小 JSON，不透传第三方输出。
        try (PrintStream silent = new PrintStream(OutputStream.nullOutputStream())) {
            System.setOut(silent);
            System.setErr(silent);
            try {
                require(args.length == 3);
                signer = verify(Path.of(args[0]), args[1], args[2]);
                hap = args[1];
                verified = true;
            } catch (Exception | LinkageError failure) {
                // 失败不输出输入路径、证书或平台异常原文。
            } finally {
                System.setOut(stdout);
                System.setErr(stderr);
            }
        }
        stdout.println("{\"schemaVersion\":1,\"signedHAP_SHA256\":\"" + hap
            + "\",\"actualSignerDER_SHA256\":\"" + signer + "\",\"signerCount\":"
            + (verified ? 1 : 0) + ",\"verified\":" + verified + "}");
        if (!verified) System.exit(1);
    }
}
