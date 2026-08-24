
import asyncio
import json
try:
    import noise
    from noise.connection import NoiseConnection
except ImportError:
    noise = None

class DP2P_Node:
    def __init__(self, is_initiator: bool, peer_static_key: bytes = None):
        self.is_initiator = is_initiator
        if noise is not None:
            self.static_keypair = noise.keys.new_keypair()
            self.protocol = NoiseConnection.from_name(b"Noise_NK_25519_ChaChaPoly_SHA256")
            if self.is_initiator:
                self.protocol.set_as_initiator()
                self.protocol.start_handshake()
                self.protocol.handshake_state.remote_static_key = peer_static_key
            else:
                self.protocol.set_as_responder()
                self.protocol.start_handshake()
        else:
            self.protocol = None

    async def connect_and_exchange(self, host: str, port: int, data_to_send: dict) -> dict:
        if not self.protocol:
            raise RuntimeError("Noise kütüphanesi yüklü değil.")
        reader, writer = await asyncio.open_connection(host, port)
        if self.is_initiator:
            message = self.protocol.write_message()
            writer.write(message)
            await writer.drain()
            response = await reader.read(4096)
            self.protocol.read_message(response)
        else:
            message = await reader.read(4096)
            self.protocol.read_message(message)
            response = self.protocol.write_message()
            writer.write(response)
            await writer.drain()

        if not self.protocol.handshake_finished:
            raise ConnectionError("Noise Handshake başarısız.")

        serialized_data = json.dumps(data_to_send).encode("utf-8")
        encrypted_data = self.protocol.encrypt(serialized_data)
        writer.write(len(encrypted_data).to_bytes(4, "big"))
        writer.write(encrypted_data)
        await writer.drain()
        
        response_len = int.from_bytes(await reader.read(4), "big")
        encrypted_response = await reader.read(response_len)
        decrypted_response = self.protocol.decrypt(encrypted_response)
        writer.close()
        await writer.wait_closed()
        return json.loads(decrypted_response.decode("utf-8"))

