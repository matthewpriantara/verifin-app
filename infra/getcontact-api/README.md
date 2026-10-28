# getcontact-api

Layanan kecil di home server (`fizualinux`, Tailscale `100.82.95.50:8091`) yang membungkus
`~/Project/getcontact-cli/gtc.py`. Dipakai Verifin hanya untuk jumlah tag dan label spam per nomor.

## Privasi

Nama tampilan, email, dan isi tag tidak pernah diminta, disimpan, atau dikembalikan. Yang disimpan
hanya `sha256(nomor)`, jumlah tag, dan derajat spam. Cache 14 hari supaya kuota hemat.

## Kuota

Akun premium: 300 `search`/bulan. Layanan membatasi 10 pencarian baru/hari; sisanya dilayani cache.
Kuota habis → `{"status":"QUOTA"}`, backend Verifin memperlakukannya sebagai `UNAVAILABLE`
(tidak menambah atau mengurangi skor).

Captcha (HTTP 403) diselesaikan manual di home: `python3 ~/Project/getcontact-cli/gtc.py captcha`.

## Jalankan

```bash
cd ~/Project/verifin-app/infra/getcontact-api
cp .env.example .env          # isi GETCONTACT_API_TOKEN (openssl rand -hex 16)
docker compose up -d --build
curl -s http://100.82.95.50:8091/health
curl -s -H "X-Api-Key: <token>" "http://100.82.95.50:8091/lookup?phone=0812xxxx"
```

`compose.yml` memakai IP Tailscale, bukan `0.0.0.0`, dan `gtc.py` di-mount dari host (tidak
disalin ke repo publik ini).

## Matikan

Di `backend/.env` server: `GETCONTACT_URL=` (kosong), lalu deploy ulang backend.

## Produksi (VPS) lewat reverse tunnel

Tailnet VPS tidak bisa membuka TCP ke home, tetapi home bisa SSH ke VPS.
1. Home: pasang `gtc-tunnel.service` sebagai user service (petunjuk di kepala berkas). Tunnel membuka `127.0.0.1:8091` di VPS.
2. VPS: container backend ada di bridge Docker, jadi butuh relay dari gateway bridge ke loopback:
   ```bash
   cd ~/projects/verifin
   docker run -d --name gtc-relay --restart unless-stopped --network host \
     -v "$PWD/infra/getcontact-api/relay.py:/relay.py:ro" --entrypoint python \
     ghcr.io/matthewpriantara/verifin-app-backend:latest /relay.py
   ```
   `RELAY_LISTEN_HOST` bawaan `172.26.0.1` (gateway `verifin_default`; cek dengan `docker network inspect verifin_default`).
3. `backend/.env` VPS: `GETCONTACT_URL=http://172.26.0.1:8091` dan `GETCONTACT_TOKEN` sama dengan home.

Mematikan: kosongkan `GETCONTACT_URL` di VPS. Bila home mati, backend menerima `UNAVAILABLE` dan skor tidak berubah.
