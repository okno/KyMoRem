package dev.kymorem.android;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.os.Bundle;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicBoolean;

import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

public final class MainActivity extends Activity {
    private static final String VERSION = "0.2.0-rc2";
    private static final int PORT = 54865;
    private static final int PROTOCOL = 1;
    private static final int MAX_FRAME_BYTES = 65536;
    private static final String DEFAULT_TOKEN = "kymorem-local-default-change-me";
    private static final String SUITE_PSK = "psk-hkdf-sha256+aes-256-gcm";
    private static final String SECURE_FRAME = "secure";

    private final AtomicBoolean running = new AtomicBoolean(false);
    private AndroidClient client;
    private RemoteSurface surface;
    private TextView status;
    private EditText nameField;
    private EditText portField;
    private EditText tokenField;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = dp(16);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setGravity(Gravity.CENTER_VERTICAL);
        root.setBackgroundColor(0xff070b10);

        TextView title = new TextView(this);
        title.setText(getString(R.string.app_name) + " Android");
        title.setTextColor(0xff24e8f2);
        title.setTextSize(30);
        root.addView(title, matchWrap());

        TextView summary = new TextView(this);
        summary.setText(getString(R.string.summary));
        summary.setTextColor(0xffb8c2d6);
        summary.setTextSize(15);
        summary.setPadding(0, dp(4), 0, dp(10));
        root.addView(summary, matchWrap());

        nameField = field(getString(R.string.name_hint));
        nameField.setText("android-client");
        root.addView(nameField, matchWrap());

        portField = field(getString(R.string.port_hint));
        portField.setText(String.valueOf(PORT));
        root.addView(portField, matchWrap());

        tokenField = field(getString(R.string.token_hint));
        root.addView(tokenField, matchWrap());

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        Button start = actionButton(getString(R.string.start_listener));
        Button stop = actionButton(getString(R.string.stop_listener));
        buttons.addView(start, weightButton());
        buttons.addView(stop, weightButton());
        root.addView(buttons, matchWrap());

        surface = new RemoteSurface(this);
        root.addView(surface, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));

        status = new TextView(this);
        status.setText(getString(R.string.status_idle));
        status.setTextColor(0xff39e58c);
        status.setTextSize(13);
        status.setPadding(0, dp(10), 0, 0);
        root.addView(status, matchWrap());

        start.setOnClickListener(view -> startClient());
        stop.setOnClickListener(view -> stopClient());
        setContentView(root);
    }

    @Override
    protected void onDestroy() {
        stopClient();
        super.onDestroy();
    }

    private void startClient() {
        stopClient();
        String token = tokenField.getText().toString().trim();
        if (token.length() < 24 || DEFAULT_TOKEN.equals(token)) {
            setStatus(getString(R.string.status_bad_token));
            return;
        }
        int port = parsePort(portField.getText().toString(), PORT);
        String name = nameField.getText().toString().trim();
        if (name.isEmpty()) {
            name = "android-client";
        }
        running.set(true);
        client = new AndroidClient(name, token, port);
        new Thread(client, "KyMoRem-Android-Client").start();
        setStatus(String.format(Locale.ROOT, getString(R.string.status_listening), port));
    }

    private void stopClient() {
        running.set(false);
        if (client != null) {
            client.close();
            client = null;
        }
        if (status != null) {
            setStatus(getString(R.string.status_idle));
        }
    }

    private void setStatus(String text) {
        runOnUiThread(() -> status.setText(text));
    }

    private EditText field(String hint) {
        EditText field = new EditText(this);
        field.setHint(hint);
        field.setHintTextColor(0xff6f7b91);
        field.setTextColor(0xfff4f7fb);
        field.setTextSize(15);
        field.setSingleLine(true);
        field.setPadding(dp(12), dp(6), dp(12), dp(6));
        field.setBackgroundColor(0xff111923);
        return field;
    }

    private Button actionButton(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(0xff071016);
        button.setBackgroundColor(0xff24e8f2);
        return button;
    }

    private LinearLayout.LayoutParams matchWrap() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, 0, 0, dp(8));
        return params;
    }

    private LinearLayout.LayoutParams weightButton() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
        params.setMargins(dp(2), 0, dp(2), 0);
        return params;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density);
    }

    private int parsePort(String value, int fallback) {
        try {
            int port = Integer.parseInt(value.trim());
            return Math.max(1, Math.min(65535, port));
        } catch (Exception ignored) {
            return fallback;
        }
    }

    private final class AndroidClient implements Runnable {
        private final String name;
        private final String token;
        private final int port;
        private ServerSocket serverSocket;

        AndroidClient(String name, String token, int port) {
            this.name = name;
            this.token = token;
            this.port = port;
        }

        @Override
        public void run() {
            try (ServerSocket server = new ServerSocket(port)) {
                serverSocket = server;
                while (running.get()) {
                    try (Socket socket = server.accept()) {
                        socket.setSoTimeout(20000);
                        setStatus(getString(R.string.status_handshake));
                        SecureLink link = secureAccept(socket, token, name);
                        socket.setSoTimeout(0);
                        setStatus(getString(R.string.status_connected));
                        while (running.get()) {
                            Map<String, Object> message = link.readSecureFrame();
                            if (message == null) {
                                break;
                            }
                            dispatch(link, message);
                        }
                    } catch (Exception exc) {
                        if (running.get()) {
                            setStatus(getString(R.string.status_error) + " " + exc.getMessage());
                        }
                    }
                }
            } catch (Exception exc) {
                if (running.get()) {
                    setStatus(getString(R.string.status_error) + " " + exc.getMessage());
                }
            }
        }

        void close() {
            try {
                if (serverSocket != null) {
                    serverSocket.close();
                }
            } catch (Exception ignored) {
            }
        }

        private void dispatch(SecureLink link, Map<String, Object> message) throws Exception {
            String kind = stringValue(message.get("type"));
            Map<String, Object> payload = asMap(message.get("payload"));
            if ("health_probe".equals(kind)) {
                link.send(frame("health_ack", "name", name, "os", "android", "platform", "android", "version", VERSION, "screen", surface.screen()));
            } else if ("hello".equals(kind)) {
                link.send(frame("status", "state", "connected", "name", name, "platform", "android"));
            } else if ("keepalive".equals(kind)) {
                link.send(frame("keepalive_ack", "name", name, "screen", surface.screen()));
            } else if ("enter".equals(kind)) {
                String edge = stringValue(payload.get("edge"));
                surface.enter(edge, doubleValue(payload.get("x_ratio"), 0.5), doubleValue(payload.get("y_ratio"), 0.5));
                link.send(frame("entered", "name", name, "edge", edge, "x", surface.pointerX(), "y", surface.pointerY(), "screen", surface.screen()));
            } else if ("move".equals(kind)) {
                surface.move(intValue(payload.get("dx")), intValue(payload.get("dy")));
                maybeReportEdge(link);
            } else if ("wheel".equals(kind)) {
                surface.wheel(intValue(payload.get("dx")), intValue(payload.get("dy")));
            } else if ("button".equals(kind)) {
                surface.button(stringValue(payload.get("button")), stringValue(payload.get("state")));
            } else if ("key".equals(kind)) {
                surface.key(stringValue(payload.get("key")), stringValue(payload.get("state")));
            } else if ("release".equals(kind)) {
                surface.release();
                link.send(frame("released", "name", name));
            } else if ("locate_pointer".equals(kind)) {
                link.send(frame("pointer_position", "name", name, "x", surface.pointerX(), "y", surface.pointerY(), "screen", surface.screen()));
            } else if ("clipboard_text".equals(kind)) {
                ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                clipboard.setPrimaryClip(ClipData.newPlainText("KyMoRem", stringValue(payload.get("text"))));
                link.send(frame("clipboard_ack", "mode", "text"));
            } else if ("clipboard_request".equals(kind)) {
                ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                String text = "";
                if (clipboard.hasPrimaryClip() && clipboard.getPrimaryClip().getItemCount() > 0) {
                    CharSequence value = clipboard.getPrimaryClip().getItemAt(0).coerceToText(MainActivity.this);
                    text = value == null ? "" : value.toString();
                }
                link.send(frame("clipboard_text", "text", text, "source", name));
            }
        }

        private void maybeReportEdge(SecureLink link) throws Exception {
            String edge = surface.edge();
            if (!edge.isEmpty() && surface.canReportEdge()) {
                link.send(frame("edge", "edge", edge, "x", surface.pointerX(), "y", surface.pointerY(), "left", 0, "top", 0, "width", surface.width(), "height", surface.height()));
            }
        }
    }

    private final class RemoteSurface extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private float pointerX = 48;
        private float pointerY = 48;
        private String state = "standby";
        private String lastKey = "";
        private String lastButton = "";
        private int wheelSum = 0;
        private long lastEdgeReport = 0L;

        RemoteSurface(Context context) {
            super(context);
            setBackgroundColor(0xff0b1118);
        }

        void enter(String edge, double xr, double yr) {
            runOnUiThread(() -> {
                int w = Math.max(1, getWidth());
                int h = Math.max(1, getHeight());
                pointerX = (float) (clamp(xr) * (w - 1));
                pointerY = (float) (clamp(yr) * (h - 1));
                if ("left".equals(edge)) pointerX = 8;
                if ("right".equals(edge)) pointerX = w - 9;
                if ("up".equals(edge)) pointerY = 8;
                if ("down".equals(edge)) pointerY = h - 9;
                state = "remote";
                invalidate();
            });
        }

        void move(int dx, int dy) {
            runOnUiThread(() -> {
                pointerX = Math.max(0, Math.min(Math.max(0, getWidth() - 1), pointerX + dx));
                pointerY = Math.max(0, Math.min(Math.max(0, getHeight() - 1), pointerY + dy));
                invalidate();
            });
        }

        void wheel(int dx, int dy) {
            runOnUiThread(() -> {
                wheelSum = Math.max(-9999, Math.min(9999, wheelSum + dx + dy));
                invalidate();
            });
        }

        void button(String button, String stateValue) {
            runOnUiThread(() -> {
                lastButton = button + " " + stateValue;
                invalidate();
            });
        }

        void key(String key, String stateValue) {
            runOnUiThread(() -> {
                lastKey = key + " " + stateValue;
                invalidate();
            });
        }

        void release() {
            runOnUiThread(() -> {
                state = "standby";
                lastButton = "";
                lastKey = "";
                wheelSum = 0;
                invalidate();
            });
        }

        int pointerX() {
            return Math.round(pointerX);
        }

        int pointerY() {
            return Math.round(pointerY);
        }

        int width() {
            return Math.max(1, getWidth());
        }

        int height() {
            return Math.max(1, getHeight());
        }

        String screen() {
            return width() + "x" + height();
        }

        String edge() {
            int w = width();
            int h = height();
            if (pointerX <= 1) return "left";
            if (pointerX >= w - 2) return "right";
            if (pointerY <= 1) return "up";
            if (pointerY >= h - 2) return "down";
            return "";
        }

        boolean canReportEdge() {
            long now = System.currentTimeMillis();
            if (now - lastEdgeReport < 450) {
                return false;
            }
            lastEdgeReport = now;
            return true;
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            int w = width();
            int h = height();
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(dp(2));
            paint.setColor(0xff24e8f2);
            canvas.drawRect(2, 2, w - 2, h - 2, paint);

            paint.setStyle(Paint.Style.FILL);
            paint.setColor(0xff39e58c);
            paint.setTextSize(dp(14));
            canvas.drawText("KyMoRem Android // " + state, dp(14), dp(28), paint);
            canvas.drawText("key: " + lastKey, dp(14), dp(52), paint);
            canvas.drawText("button: " + lastButton, dp(14), dp(76), paint);
            canvas.drawText("wheel: " + wheelSum, dp(14), dp(100), paint);

            paint.setColor(0xffa56cff);
            canvas.drawCircle(pointerX, pointerY, dp(14), paint);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(dp(3));
            paint.setColor(0xff24e8f2);
            canvas.drawCircle(pointerX, pointerY, dp(22), paint);
        }
    }

    private SecureLink secureAccept(Socket socket, String token, String name) throws Exception {
        BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8));
        Map<String, Object> init = readPlain(reader);
        Map<String, Object> initPayload = asMap(init.get("payload"));
        if (!"kymorem_crypto_init".equals(init.get("type"))) {
            throw new IllegalStateException("expected crypto init");
        }
        if (!tokenFingerprint(token).equals(stringValue(initPayload.get("token_id")))) {
            throw new IllegalStateException("token fingerprint mismatch");
        }
        byte[] initNonce = unb64(stringValue(initPayload.get("nonce")));
        byte[] responseNonce = randomBytes(16);
        Map<String, Object> identity = mapOf("role", "client", "name", name, "platform", "android", "version", VERSION);
        Map<String, Object> challenge = frame(
            "kymorem_crypto_challenge",
            "suite", SUITE_PSK,
            "nonce", b64(responseNonce),
            "identity", identity,
            "capabilities", mapOf("aead", "AES-256-GCM", "hkdf", "HKDF-SHA256", "post_quantum_kem", null, "suites", listOf(SUITE_PSK))
        );
        writePlain(writer, challenge);
        byte[] transcript = concat(canonical(init), canonical(challenge));
        Map<String, Object> finish = readPlain(reader);
        Map<String, Object> finishPayload = asMap(finish.get("payload"));
        if (!"kymorem_crypto_finish".equals(finish.get("type"))) {
            throw new IllegalStateException("expected crypto finish");
        }
        if (!SUITE_PSK.equals(stringValue(finishPayload.get("suite")))) {
            throw new IllegalStateException("unsupported suite");
        }
        byte[] key = deriveSessionKey(token, initNonce, responseNonce, transcript);
        if (!proof(key, "finish", transcript).equals(stringValue(finishPayload.get("proof")))) {
            throw new IllegalStateException("invalid proof");
        }
        transcript = concat(transcript, canonical(finish));
        writePlain(writer, frame("kymorem_crypto_ack", "proof", proof(key, "ack", transcript)));
        return new SecureLink(reader, writer, key);
    }

    private static final class SecureLink {
        private final BufferedReader reader;
        private final BufferedWriter writer;
        private final byte[] key;
        private int txSeq = 0;
        private int rxSeq = 0;

        SecureLink(BufferedReader reader, BufferedWriter writer, byte[] key) {
            this.reader = reader;
            this.writer = writer;
            this.key = key;
        }

        synchronized void send(Map<String, Object> message) throws Exception {
            txSeq += 1;
            byte[] nonce = randomBytes(12);
            byte[] cipher = aesGcmEncrypt(key, nonce, canonical(message), bytes("KyMoRem secure frame v1:" + txSeq));
            writePlain(writer, frame(SECURE_FRAME, "suite", SUITE_PSK, "seq", txSeq, "nonce", b64(nonce), "data", b64(cipher)));
        }

        Map<String, Object> readSecureFrame() throws Exception {
            Map<String, Object> outer = readPlain(reader);
            if (outer == null) {
                return null;
            }
            if (!SECURE_FRAME.equals(outer.get("type"))) {
                throw new IllegalStateException("unexpected plaintext frame");
            }
            Map<String, Object> payload = asMap(outer.get("payload"));
            int seq = intValue(payload.get("seq"));
            if (seq <= rxSeq) {
                throw new IllegalStateException("replay or out-of-order frame");
            }
            rxSeq = seq;
            byte[] plain = aesGcmDecrypt(
                key,
                unb64(stringValue(payload.get("nonce"))),
                unb64(stringValue(payload.get("data"))),
                bytes("KyMoRem secure frame v1:" + seq)
            );
            return asMap(new JSONObject(new String(plain, StandardCharsets.UTF_8)));
        }
    }

    private static Map<String, Object> frame(String kind, Object... pairs) {
        Map<String, Object> payload = new TreeMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) {
            payload.put(String.valueOf(pairs[index]), pairs[index + 1]);
        }
        Map<String, Object> frame = new TreeMap<>();
        frame.put("protocol", PROTOCOL);
        frame.put("type", kind);
        frame.put("ts", System.currentTimeMillis());
        frame.put("payload", payload);
        return frame;
    }

    private static Map<String, Object> readPlain(BufferedReader reader) throws Exception {
        String line = reader.readLine();
        if (line == null) {
            return null;
        }
        if (line.length() > MAX_FRAME_BYTES) {
            throw new IllegalStateException("frame too large");
        }
        return asMap(new JSONObject(line));
    }

    private static void writePlain(BufferedWriter writer, Map<String, Object> message) throws Exception {
        writer.write(canonicalString(message));
        writer.write("\n");
        writer.flush();
    }

    private static byte[] deriveSessionKey(String token, byte[] initNonce, byte[] responseNonce, byte[] transcript) throws Exception {
        byte[] psk = hkdf(bytes(token), bytes("KyMoRem token salt v1"), bytes("session psk"), 32);
        byte[] secret = concat(bytes("KyMoRem session v1"), bytes(SUITE_PSK), psk);
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        byte[] salt = sha.digest(concat(initNonce, responseNonce, transcript));
        return hkdf(secret, salt, bytes("KyMoRem secure transport key v1"), 32);
    }

    private static String tokenFingerprint(String token) throws Exception {
        return hex(hmac(bytes("KyMoRem token id v1"), bytes(token))).substring(0, 32);
    }

    private static String proof(byte[] key, String label, byte[] transcript) throws Exception {
        return hex(hmac(key, concat(bytes(label), transcript)));
    }

    private static byte[] hkdf(byte[] input, byte[] salt, byte[] info, int length) throws Exception {
        byte[] prk = hmac(salt, input);
        byte[] result = new byte[length];
        byte[] t = new byte[0];
        int offset = 0;
        int counter = 1;
        while (offset < length) {
            t = hmac(prk, concat(t, info, new byte[]{(byte) counter}));
            int copy = Math.min(t.length, length - offset);
            System.arraycopy(t, 0, result, offset, copy);
            offset += copy;
            counter += 1;
        }
        return result;
    }

    private static byte[] hmac(byte[] key, byte[] data) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key, "HmacSHA256"));
        return mac.doFinal(data);
    }

    private static byte[] aesGcmEncrypt(byte[] key, byte[] nonce, byte[] plain, byte[] aad) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(key, "AES"), new GCMParameterSpec(128, nonce));
        cipher.updateAAD(aad);
        return cipher.doFinal(plain);
    }

    private static byte[] aesGcmDecrypt(byte[] key, byte[] nonce, byte[] cipherText, byte[] aad) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(key, "AES"), new GCMParameterSpec(128, nonce));
        cipher.updateAAD(aad);
        return cipher.doFinal(cipherText);
    }

    private static byte[] canonical(Map<String, Object> value) {
        return bytes(canonicalString(value));
    }

    private static String canonicalString(Object value) {
        if (value == null) return "null";
        if (value instanceof Map) {
            TreeMap<String, Object> sorted = new TreeMap<>();
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                sorted.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            StringBuilder out = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<String, Object> entry : sorted.entrySet()) {
                if (!first) out.append(",");
                first = false;
                out.append(JSONObject.quote(entry.getKey())).append(":").append(canonicalString(entry.getValue()));
            }
            return out.append("}").toString();
        }
        if (value instanceof List) {
            StringBuilder out = new StringBuilder("[");
            boolean first = true;
            for (Object item : (List<?>) value) {
                if (!first) out.append(",");
                first = false;
                out.append(canonicalString(item));
            }
            return out.append("]").toString();
        }
        if (value instanceof Number || value instanceof Boolean) {
            return String.valueOf(value);
        }
        return JSONObject.quote(String.valueOf(value));
    }

    private static Map<String, Object> asMap(Object value) {
        if (value instanceof Map) {
            TreeMap<String, Object> out = new TreeMap<>();
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                out.put(String.valueOf(entry.getKey()), normalizeJson(entry.getValue()));
            }
            return out;
        }
        if (value instanceof JSONObject) {
            TreeMap<String, Object> out = new TreeMap<>();
            JSONObject object = (JSONObject) value;
            Iterator<String> keys = object.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                out.put(key, normalizeJson(object.opt(key)));
            }
            return out;
        }
        return new TreeMap<>();
    }

    private static Object normalizeJson(Object value) {
        if (value == JSONObject.NULL) return null;
        if (value instanceof JSONObject) return asMap(value);
        if (value instanceof JSONArray) {
            JSONArray array = (JSONArray) value;
            ArrayList<Object> out = new ArrayList<>();
            for (int i = 0; i < array.length(); i++) out.add(normalizeJson(array.opt(i)));
            return out;
        }
        return value;
    }

    private static Map<String, Object> mapOf(Object... pairs) {
        Map<String, Object> out = new TreeMap<>();
        for (int i = 0; i + 1 < pairs.length; i += 2) out.put(String.valueOf(pairs[i]), pairs[i + 1]);
        return out;
    }

    private static List<Object> listOf(Object... values) {
        ArrayList<Object> out = new ArrayList<>();
        for (Object value : values) out.add(value);
        return out;
    }

    private static byte[] concat(byte[]... chunks) {
        int length = 0;
        for (byte[] chunk : chunks) length += chunk.length;
        ByteBuffer buffer = ByteBuffer.allocate(length);
        for (byte[] chunk : chunks) buffer.put(chunk);
        return buffer.array();
    }

    private static String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private static int intValue(Object value) {
        if (value instanceof Number) return ((Number) value).intValue();
        try {
            return Integer.parseInt(stringValue(value));
        } catch (Exception ignored) {
            return 0;
        }
    }

    private static double doubleValue(Object value, double fallback) {
        if (value instanceof Number) return ((Number) value).doubleValue();
        try {
            return Double.parseDouble(stringValue(value));
        } catch (Exception ignored) {
            return fallback;
        }
    }

    private static double clamp(double value) {
        return Math.max(0.0, Math.min(1.0, value));
    }

    private static byte[] bytes(String value) {
        return value.getBytes(StandardCharsets.UTF_8);
    }

    private static byte[] randomBytes(int length) {
        byte[] value = new byte[length];
        new SecureRandom().nextBytes(value);
        return value;
    }

    private static String b64(byte[] value) {
        return Base64.encodeToString(value, Base64.URL_SAFE | Base64.NO_WRAP);
    }

    private static byte[] unb64(String value) {
        return Base64.decode(value, Base64.URL_SAFE | Base64.NO_WRAP);
    }

    private static String hex(byte[] value) {
        StringBuilder out = new StringBuilder();
        for (byte item : value) out.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        return out.toString();
    }
}
