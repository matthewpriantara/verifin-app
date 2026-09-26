const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const IMAGES_DIR = path.join(__dirname, '../../proposal-verifin/images');
const BASE_URL = 'http://localhost:3000';

const TEST_TEXT = `The Biker Shop
membuka lowongan
Marketing Officer - Sales Counter - Mekanik Motor
The Biker Shop saat ini membuka lowongan kerja untuk posisi sebagai :

Marketing Officer
Sales Counter
Mekanik Motor
Ringkasan
Pendidikan: SMA / SMK
Pengalaman: 0 - 2 Tahun
Gender: Pria/Wanita
Besaran Gaji: Kompetitif
Lokasi Kerja: The Biker Shop Jogja, Jl. Parangtritis No.38, Mantrijeron, Kec. Mantrijeron, Kota Jogja, DIY - 55143
Kirim Lamaran
Formulir: https://forms.gle/N6mfqUbVnC2JF68y6
Email: hrdthebikershop@gmail.com
No. Telepon: +6285738325536`;

async function delay(ms) { return new Promise(r => setTimeout(r, ms)); }
async function screenshot(page, filename) {
  await page.screenshot({ path: path.join(IMAGES_DIR, filename), fullPage: true });
  console.log(`  Saved: ${filename}`);
}

async function waitForResult(page, timeoutMs = 300000) {
  console.log('  Polling for result...');
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const resultContent = await page.$('text=/Faktor Penilaian|Rekomendasi Sebelum|Perusahaan & Lokasi/i');
      if (resultContent) { console.log('  Result detected!'); await delay(3000); return true; }
    } catch (e) {}
    await delay(5000);
    const elapsed = Math.round((Date.now() - start) / 1000);
    if (elapsed % 15 === 0) process.stdout.write(`  ${elapsed}s...`);
  }
  console.log('  Timeout!');
  return false;
}

async function main() {
  console.log('=== Verifin Complete Screenshot Suite ===');
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'id-ID' });
  const page = await ctx.newPage();

  try {
    // ========== 1. FORM INPUT SCREENSHOTS ==========
    console.log('\n--- 1. Form Input: TEXT ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(2000);
    
    // Fill text and screenshot with content visible
    const textarea = await page.$('textarea');
    if (textarea) {
      await textarea.fill(TEST_TEXT);
      await delay(500);
      await screenshot(page, 'tes text.png');
      // Clear for next test
      await textarea.fill('');
    }

    console.log('\n--- 2. Form Input: GAMBAR ---');
    const ocrPath = path.join(__dirname, '../../ocr.webp');
    if (fs.existsSync(ocrPath)) {
      const fileInput = await page.$('input[type="file"]');
      if (fileInput) {
        await fileInput.setInputFiles(ocrPath);
        await delay(1000);
        await screenshot(page, 'tes gambar.png');
      }
    }

    console.log('\n--- 3. Form Input: LINK ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(2000);
    const textarea2 = await page.$('textarea');
    if (textarea2) {
      await textarea2.fill('https://www.threads.com/@andre.patra/post/Db8RPMwiZuD');
      await delay(500);
      await screenshot(page, 'tes link.png');
      await textarea2.fill('');
    }

    // ========== 4. LOADING MODAL SCREENSHOT ==========
    console.log('\n--- 4. Loading Modal ---');
    // Fill text and click to trigger loading
    const textarea3 = await page.$('textarea');
    if (textarea3) {
      await textarea3.fill(TEST_TEXT);
      await delay(500);
      const btn = await page.$('button:has-text("Verifikasi")');
      if (btn) {
        await btn.click({ force: true });
        // Wait for modal to appear (check for step indicators)
        await delay(3000);
        await screenshot(page, 'mockup-loading.png');
        console.log('  Loading modal captured');
        // Wait for result
        await waitForResult(page);
      }
    }

    // ========== 5. TEXT RESULT (reuse from loading test) ==========
    console.log('\n--- 5. Text Result (The Biker Shop) ---');
    await page.evaluate(() => window.scrollTo(0, 0));
    await delay(500);
    await screenshot(page, 'hasil text 1.png');
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
    await delay(500);
    await screenshot(page, 'hasil text 2.png');

    // ========== 6. OCR/GAMBAR RESULT ==========
    console.log('\n--- 6. OCR/Gambar Result (VinFast) ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(2000);
    if (fs.existsSync(ocrPath)) {
      const fileInput2 = await page.$('input[type="file"]');
      if (fileInput2) {
        await fileInput2.setInputFiles(ocrPath);
        await delay(1000);
        const btn2 = await page.$('button:has-text("Verifikasi")');
        if (btn2) {
          await btn2.click({ force: true });
          await waitForResult(page);
          await page.evaluate(() => window.scrollTo(0, 0));
          await delay(500);
          await screenshot(page, 'hasil gambar 1.png');
          await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
          await delay(500);
          await screenshot(page, 'hasil gambar 2.png');
        }
      }
    }

    // ========== 7. LINK RESULT ==========
    console.log('\n--- 7. Link Result (SISI) ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(2000);
    const textarea4 = await page.$('textarea');
    if (textarea4) {
      await textarea4.fill('https://www.threads.com/@andre.patra/post/Db8RPMwiZuD');
      await delay(500);
      const btn3 = await page.$('button:has-text("Verifikasi")');
      if (btn3) {
        await btn3.click({ force: true });
        await waitForResult(page);
        await page.evaluate(() => window.scrollTo(0, 0));
        await delay(500);
        await screenshot(page, 'hasil link 1.png');
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
        await delay(500);
        await screenshot(page, 'hasil link 2.png');
      }
    }

    // ========== 8. NEGATIVE CASE ==========
    console.log('\n--- 8. Negative Case (Scam) ---');
    const scamText = `Dibutuhkan Admin Online WFH
Gaji 8-15 juta/bulan
Syarat: min SMA, punya HP Android
Hubungi: 0812-3456-7890 (Budi - HRD PT Sukses Mandiri)
Langsung kerja, tidak perlu pengalaman
Kirim foto dan KTP sekarang ke WhatsApp
Transfer biaya pendaftaran Rp 500.000 ke rekening BCA 1234567890`;
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(2000);
    const textarea5 = await page.$('textarea');
    if (textarea5) {
      await textarea5.fill(scamText);
      await delay(500);
      const btn4 = await page.$('button:has-text("Verifikasi")');
      if (btn4) {
        await btn4.click({ force: true });
        await waitForResult(page);
        await page.evaluate(() => window.scrollTo(0, 0));
        await delay(500);
        await screenshot(page, 'hasil test negatif.png');
      }
    }

    // ========== 9. COMMUNITY (Lapor Komunitas) ==========
    console.log('\n--- 9. Community (Lapor Komunitas) ---');
    await page.goto(`${BASE_URL}/report`, { waitUntil: 'networkidle' });
    await delay(2000);
    await screenshot(page, 'mockup-community.png');

    // ========== 10. RIWAYAT ==========
    console.log('\n--- 10. Riwayat ---');
    await page.goto(`${BASE_URL}/report-job`, { waitUntil: 'networkidle' });
    await delay(2000);
    await screenshot(page, 'mockup-riwayat.png');

    console.log('\n=== ALL DONE ===');
  } catch (err) {
    console.error('Error:', err.message);
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
