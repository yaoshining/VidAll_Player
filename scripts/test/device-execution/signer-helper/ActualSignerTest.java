import com.ohos.hapsigntool.hap.verify.VerifyResult;
import java.math.BigInteger;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Date;
import java.util.HexFormat;
import java.util.List;
import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.CMSSignedDataGenerator;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;
import org.bouncycastle.util.CollectionStore;

/** 全部证书和密钥只在内存生成；仅验证真实 SID 选择函数，不冒充 HAP 验签。 */
public final class ActualSignerTest {
    record Fixture(KeyPair keys, X509CertificateHolder cert) {}
    interface Check { void run() throws Exception; }
    static int passed;
    static int failed;
    static Fixture fixture(int serial) throws Exception {
        return fixture(serial, new Date(0), new Date(4102444800000L));
    }
    static Fixture fixture(int serial, Date before, Date after) throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("EC");
        generator.initialize(256);
        KeyPair keys = generator.generateKeyPair();
        X500Name name = new X500Name("CN=Temporary SID fixture " + serial);
        X509CertificateHolder cert = new JcaX509v3CertificateBuilder(name,
            BigInteger.valueOf(serial), before, after,
            name, keys.getPublic()).build(new JcaContentSignerBuilder("SHA256withECDSA")
                .build(keys.getPrivate()));
        return new Fixture(keys, cert);
    }
    static String hash(Fixture value) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
            .digest(value.cert().getEncoded()));
    }
    static VerifyResult result(List<Fixture> signers, List<Fixture> certificates) throws Exception {
        CMSSignedDataGenerator gen = new CMSSignedDataGenerator();
        for (Fixture value : signers) {
            gen.addSignerInfoGenerator(new JcaSignerInfoGeneratorBuilder(
                new JcaDigestCalculatorProviderBuilder().build()).build(
                    new JcaContentSignerBuilder("SHA256withECDSA").build(value.keys().getPrivate()),
                    value.cert()));
        }
        gen.addCertificates(new CollectionStore<>(certificates.stream().map(Fixture::cert).toList()));
        CMSSignedData cms = gen.generate(new CMSProcessableByteArray(new byte[]{1, 2, 3}), true);
        // 官方 HAP 验签结果的真实类型；此 verified 是测试前提，并非 HAP 实测结论。
        VerifyResult result = new VerifyResult(true, 10000, "synthetic SID boundary only");
        result.setSignerInfos(new ArrayList<>(cms.getSignerInfos().getSigners()));
        result.setCertificateHolderStore(cms.getCertificates());
        return result;
    }
    static void reject(Check check) throws Exception {
        try { check.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("must reject");
    }
    static void test(String name, Check check) {
        try { check.run(); passed++; System.out.println("PASS " + name); }
        catch (Throwable failure) { failed++; System.out.println("FAIL " + name + " " + failure.getClass().getSimpleName()); }
    }
    static void equal(String actual, String expected) {
        if (!actual.equals(expected)) throw new AssertionError("wrong actual signer");
    }
    public static void main(String[] ignored) throws Exception {
        Fixture a = fixture(1), b = fixture(2);
        String expected = hash(a);
        test("actual-signer", () -> equal(ActualSigner.selectSigner(result(List.of(a), List.of(a)), expected), expected));
        test("unordered-extra-certificate", () -> equal(ActualSigner.selectSigner(result(List.of(a), List.of(b, a)), expected), expected));
        test("approved-only-extra-member", () -> reject(() -> ActualSigner.selectSigner(result(List.of(b), List.of(a, b)), expected)));
        test("wrong-approved-certificate", () -> reject(() -> ActualSigner.selectSigner(result(List.of(a), List.of(a)), hash(b))));
        test("multiple-signers", () -> reject(() -> ActualSigner.selectSigner(result(List.of(a, b), List.of(a, b)), expected)));
        test("missing-signer", () -> { VerifyResult r = result(List.of(a), List.of(a)); r.setSignerInfos(List.of()); reject(() -> ActualSigner.selectSigner(r, expected)); });
        test("missing-sid-certificate", () -> { VerifyResult r = result(List.of(a), List.of(a)); r.setCertificateHolderStore(new CollectionStore<>(List.of(b.cert()))); reject(() -> ActualSigner.selectSigner(r, expected)); });
        test("ambiguous-sid-certificate", () -> { VerifyResult r = result(List.of(a), List.of(a)); r.setCertificateHolderStore(new CollectionStore<>(List.of(a.cert(), a.cert()))); reject(() -> ActualSigner.selectSigner(r, expected)); });
        test("official-verification-failed", () -> { VerifyResult r = result(List.of(a), List.of(a)); r.setIsResult(false); reject(() -> ActualSigner.selectSigner(r, expected)); });
        test("malformed-approved-hash", () -> reject(() -> ActualSigner.selectSigner(result(List.of(a), List.of(a)), "unapproved")));
        test("expired-signer-certificate", () -> { Fixture expired = fixture(3, new Date(0), new Date(1)); reject(() -> ActualSigner.selectSigner(result(List.of(expired), List.of(expired)), hash(expired))); });
        test("future-signer-certificate", () -> { long now = System.currentTimeMillis(); Fixture future = fixture(4, new Date(now+86400000L), new Date(now+172800000L)); reject(() -> ActualSigner.selectSigner(result(List.of(future), List.of(future)), hash(future))); });
        System.out.println("RESULT passed=" + passed + " failed=" + failed + " realHapVerified=false");
        if (failed != 0) System.exit(1);
    }
}
