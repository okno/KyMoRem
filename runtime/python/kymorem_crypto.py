from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import socket
from dataclasses import dataclass
from typing import Any

from kymorem_common import DEFAULT_TOKEN, ENCODING, MAX_FRAME_BYTES, PROTOCOL, VERSION, frame, read_frames, send

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
except ImportError:  # pragma: no cover - exercised on minimal systems.
    hashes = None
    AESGCM = None
    HKDF = None

try:
    from pqcrypto.kem import ml_kem_768
except ImportError:  # pragma: no cover - optional provider.
    ml_kem_768 = None


HANDSHAKE_INIT = "kymorem_crypto_init"
HANDSHAKE_CHALLENGE = "kymorem_crypto_challenge"
HANDSHAKE_FINISH = "kymorem_crypto_finish"
HANDSHAKE_ACK = "kymorem_crypto_ack"
SECURE_FRAME = "secure"
DISCOVERY_MAGIC = "KMRD1"
DISCOVERY_PORT = 54866
DISCOVERY_INTERVAL = 2.0
DISCOVERY_AAD = b"KyMoRem discovery v1"
FRAME_AAD = b"KyMoRem secure frame v1"
SUITE_MLKEM = "ml-kem-768+psk-hkdf-sha256+aes-256-gcm"
SUITE_PSK = "psk-hkdf-sha256+aes-256-gcm"
DEFAULT_SUITES = [SUITE_MLKEM, SUITE_PSK]
MIN_TOKEN_LEN = 24


class CryptoError(RuntimeError):
    pass


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("ascii"))


def canonical(message: dict[str, Any]) -> bytes:
    return json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(ENCODING)


def crypto_available() -> bool:
    return AESGCM is not None and HKDF is not None and hashes is not None


def pq_available() -> bool:
    return ml_kem_768 is not None


def crypto_capabilities() -> dict[str, Any]:
    return {
        "aead": "AES-256-GCM" if crypto_available() else "missing",
        "hkdf": "HKDF-SHA256" if crypto_available() else "missing",
        "post_quantum_kem": "ML-KEM-768" if pq_available() else None,
        "suites": supported_suites(),
    }


def supported_suites() -> list[str]:
    if not crypto_available():
        return []
    suites = [SUITE_PSK]
    if pq_available():
        suites.insert(0, SUITE_MLKEM)
    return suites


def token_fingerprint(token: str) -> str:
    return hmac.new(b"KyMoRem token id v1", token.encode(ENCODING), hashlib.sha256).hexdigest()[:32]


def validate_token(token: str) -> None:
    if not token:
        raise CryptoError("empty KyMoRem token is not allowed")
    if token == DEFAULT_TOKEN and os.environ.get("KYMOREM_ALLOW_DEFAULT_TOKEN") != "1":
        raise CryptoError("refusing the development default token; set KYMOREM_TOKEN/config token")
    if len(token) < MIN_TOKEN_LEN:
        raise CryptoError(f"KyMoRem token must be at least {MIN_TOKEN_LEN} characters")


def _require_crypto() -> None:
    if not crypto_available():
        raise CryptoError("cryptography is required for KyMoRem secure transport")


def _hkdf(secret: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    _require_crypto()
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(secret)


def _token_secret(token: str, context: bytes) -> bytes:
    validate_token(token)
    return _hkdf(token.encode(ENCODING), b"KyMoRem token salt v1", context)


def _derive_session_key(suite: str, token: str, kem_secret: bytes, init_nonce: bytes, response_nonce: bytes, transcript: bytes) -> bytes:
    psk = _token_secret(token, b"session psk")
    secret = b"KyMoRem session v1" + suite.encode("ascii") + psk + kem_secret
    salt = hashlib.sha256(init_nonce + response_nonce + transcript).digest()
    return _hkdf(secret, salt, b"KyMoRem secure transport key v1")


def _proof(key: bytes, label: bytes, transcript: bytes) -> str:
    return hmac.new(key, label + transcript, hashlib.sha256).hexdigest()


def _read_one_plain(sock: socket.socket, timeout: float = 10.0) -> dict[str, Any]:
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    buffer = b""
    try:
        while b"\n" not in buffer:
            chunk = sock.recv(65536)
            if not chunk:
                raise CryptoError("connection closed during handshake")
            buffer += chunk
            if len(buffer) > MAX_FRAME_BYTES:
                raise CryptoError("handshake frame exceeds maximum size")
        line, _rest = buffer.split(b"\n", 1)
        return json.loads(line.decode(ENCODING))
    finally:
        sock.settimeout(old_timeout)


@dataclass
class SecureJsonLink:
    sock: socket.socket
    key: bytes
    suite: str
    peer: dict[str, Any]
    tx_seq: int = 0
    rx_seq: int = 0

    def send(self, message: dict[str, Any]) -> None:
        self.tx_seq += 1
        nonce = os.urandom(12)
        plaintext = canonical(message)
        aad = FRAME_AAD + b":" + str(self.tx_seq).encode("ascii")
        ciphertext = AESGCM(self.key).encrypt(nonce, plaintext, aad)
        send(
            self.sock,
            frame(
                SECURE_FRAME,
                suite=self.suite,
                seq=self.tx_seq,
                nonce=b64(nonce),
                data=b64(ciphertext),
            ),
        )

    def read_frames(self):
        for outer in read_frames(self.sock):
            if outer.get("type") != SECURE_FRAME:
                raise CryptoError(f"unexpected plaintext frame after secure handshake: {outer.get('type')}")
            payload = outer.get("payload", {})
            if payload.get("suite") != self.suite:
                raise CryptoError("secure frame suite mismatch")
            seq = int(payload.get("seq", 0))
            if seq <= self.rx_seq:
                raise CryptoError("secure frame replay or out-of-order sequence")
            self.rx_seq = seq
            nonce = unb64(str(payload.get("nonce", "")))
            ciphertext = unb64(str(payload.get("data", "")))
            aad = FRAME_AAD + b":" + str(seq).encode("ascii")
            plaintext = AESGCM(self.key).decrypt(nonce, ciphertext, aad)
            yield json.loads(plaintext.decode(ENCODING))


def secure_connect(sock: socket.socket, token: str, identity: dict[str, Any]) -> SecureJsonLink:
    _require_crypto()
    validate_token(token)
    init_nonce = os.urandom(16)
    init = frame(
        HANDSHAKE_INIT,
        version=VERSION,
        role=identity.get("role", "host"),
        name=identity.get("name", "KyMoRem host"),
        nonce=b64(init_nonce),
        token_id=token_fingerprint(token),
        suites=supported_suites(),
        capabilities=crypto_capabilities(),
    )
    send(sock, init)
    challenge = _read_one_plain(sock)
    if challenge.get("type") != HANDSHAKE_CHALLENGE:
        raise CryptoError(f"expected {HANDSHAKE_CHALLENGE}, got {challenge.get('type')}")
    payload = challenge.get("payload", {})
    suite = str(payload.get("suite", ""))
    response_nonce = unb64(str(payload.get("nonce", "")))
    transcript = canonical(init) + canonical(challenge)

    kem_secret = b""
    finish_payload: dict[str, Any] = {"suite": suite}
    if suite == SUITE_MLKEM:
        if not pq_available():
            raise CryptoError("peer selected ML-KEM but local provider is unavailable")
        ciphertext, kem_secret = ml_kem_768.encrypt(unb64(str(payload.get("public_key", ""))))
        finish_payload["kem_ciphertext"] = b64(ciphertext)
    elif suite != SUITE_PSK:
        raise CryptoError(f"unsupported crypto suite: {suite}")

    session_key = _derive_session_key(suite, token, kem_secret, init_nonce, response_nonce, transcript)
    finish_payload["proof"] = _proof(session_key, b"finish", transcript)
    finish = frame(HANDSHAKE_FINISH, **finish_payload)
    send(sock, finish)
    transcript += canonical(finish)

    ack = _read_one_plain(sock)
    if ack.get("type") != HANDSHAKE_ACK:
        raise CryptoError(f"expected {HANDSHAKE_ACK}, got {ack.get('type')}")
    if not hmac.compare_digest(str(ack.get("payload", {}).get("proof", "")), _proof(session_key, b"ack", transcript)):
        raise CryptoError("invalid secure handshake acknowledgement")
    return SecureJsonLink(sock=sock, key=session_key, suite=suite, peer=payload.get("identity", {}))


def secure_accept(sock: socket.socket, token: str, identity: dict[str, Any]) -> SecureJsonLink:
    _require_crypto()
    validate_token(token)
    init = _read_one_plain(sock)
    if init.get("type") != HANDSHAKE_INIT:
        raise CryptoError(f"expected {HANDSHAKE_INIT}, got {init.get('type')}")
    payload = init.get("payload", {})
    if not hmac.compare_digest(str(payload.get("token_id", "")), token_fingerprint(token)):
        raise CryptoError("token fingerprint mismatch")
    peer_suites = payload.get("suites", [])
    local_suites = supported_suites()
    suite = next((candidate for candidate in local_suites if candidate in peer_suites), None)
    if not suite:
        raise CryptoError("no shared secure transport suite")

    init_nonce = unb64(str(payload.get("nonce", "")))
    response_nonce = os.urandom(16)
    kem_secret = b""
    secret_key = None
    challenge_payload: dict[str, Any] = {
        "suite": suite,
        "nonce": b64(response_nonce),
        "identity": identity,
        "capabilities": crypto_capabilities(),
    }
    if suite == SUITE_MLKEM:
        public_key, secret_key = ml_kem_768.generate_keypair()
        challenge_payload["public_key"] = b64(public_key)

    challenge = frame(HANDSHAKE_CHALLENGE, **challenge_payload)
    send(sock, challenge)
    transcript = canonical(init) + canonical(challenge)

    finish = _read_one_plain(sock)
    if finish.get("type") != HANDSHAKE_FINISH:
        raise CryptoError(f"expected {HANDSHAKE_FINISH}, got {finish.get('type')}")
    finish_payload = finish.get("payload", {})
    if finish_payload.get("suite") != suite:
        raise CryptoError("secure transport suite changed during handshake")
    if suite == SUITE_MLKEM:
        kem_secret = ml_kem_768.decrypt(secret_key, unb64(str(finish_payload.get("kem_ciphertext", ""))))

    session_key = _derive_session_key(suite, token, kem_secret, init_nonce, response_nonce, transcript)
    if not hmac.compare_digest(str(finish_payload.get("proof", "")), _proof(session_key, b"finish", transcript)):
        raise CryptoError("invalid secure handshake proof")
    transcript += canonical(finish)

    send(sock, frame(HANDSHAKE_ACK, proof=_proof(session_key, b"ack", transcript)))
    return SecureJsonLink(sock=sock, key=session_key, suite=suite, peer=payload)


def encrypt_discovery(token: str, payload: dict[str, Any]) -> bytes:
    _require_crypto()
    validate_token(token)
    nonce = os.urandom(12)
    key = _token_secret(token, b"discovery broadcast")
    ciphertext = AESGCM(key).encrypt(nonce, canonical(payload), DISCOVERY_AAD)
    outer = {
        "magic": DISCOVERY_MAGIC,
        "protocol": PROTOCOL,
        "kid": token_fingerprint(token),
        "nonce": b64(nonce),
        "data": b64(ciphertext),
    }
    return canonical(outer)


def decrypt_discovery(token: str, datagram: bytes) -> dict[str, Any]:
    _require_crypto()
    validate_token(token)
    if len(datagram) > MAX_FRAME_BYTES:
        raise CryptoError("discovery datagram exceeds maximum size")
    outer = json.loads(datagram.decode(ENCODING))
    if outer.get("magic") != DISCOVERY_MAGIC:
        raise CryptoError("not a KyMoRem discovery datagram")
    if not hmac.compare_digest(str(outer.get("kid", "")), token_fingerprint(token)):
        raise CryptoError("discovery token fingerprint mismatch")
    key = _token_secret(token, b"discovery broadcast")
    plaintext = AESGCM(key).decrypt(unb64(str(outer["nonce"])), unb64(str(outer["data"])), DISCOVERY_AAD)
    return json.loads(plaintext.decode(ENCODING))
