import socket
from datetime import datetime
from plyer import notification

# Server konfigurasiýasy
SERVER_IP = "0.0.0.0"  # Server ähli IP-lere garaşar
SERVER_PORT = 80     # Port bellemeli

def start_server():
    """Serveri başlat we duýduryşlaryny kabul et"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((SERVER_IP, SERVER_PORT))  # Server IP we port bilen baglanýar
        s.listen()  # Klientden baglanyşyklary kabul et
        print(f"Server: '{SERVER_IP}:{SERVER_PORT}' salgasynda işledi we klienti garaşýar...")

        conn, addr = s.accept()  # Klient baglananda kabul edýär
        with conn:
            print(f"Server: Bağlanýan kompýuter: {addr}")
            while True:
                # Klientden maglumat almak
                data = conn.recv(1024)  # Max. 1024 bayt almak
                if not data:
                    break
                # Maglumaty çöz we görkeziň
                message = data.decode('utf-8')
                print(f"Server: Alnan maglumat:\n{message}")

                # Duýduryş bermek
                send_notification(message)

def send_notification(message: str):
    """Duýduryş bermek"""
    notification.notify(
        title="Gözleg Maglumaty",
        message=message,
        timeout=10  # Duýduryşyň dowam ediş wagty (sekundlar)
    )

if __name__ == "__main__":
    start_server()
