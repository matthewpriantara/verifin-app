const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const IMAGES_DIR = path.join(__dirname, '../../proposal-verifin/images');
const BASE_URL = 'http://localhost:3000';

// Test data
const TEST_TEXT = `The Biker Shop
membuka lowongan
Marketing Officer - Sales Counter - Mekanik Motor
The Biker Shop saat ini membuka lowongan kerja untuk posisi sebagai :

Marketing Officer
Sales Counter
Mekanik Motor
Ringkasan
Pendidikan:
SMA / SMK
Pengalaman:
0 - 2 Tahun
Gender:
Pria/Wanita
Besaran Gaji:
Kompetitif
Lokasi Kerja:
The Biker Shop Jogja, Jl. Parangtritis No.38, Mantrijeron, Kec. Mantrijeron, Kota Jogja, DIY - 55143
Syarat Pekerjaan
Marketing Officer
Tertarik dan menyukai dunia otomotif
Komunikatif dan dapat bekerja secara individu maupun tim
Berorientasi pada target dan hasil penjualan
Jujur, disiplin, dan bertanggung jawab
Memiliki SIM C aktif
Mampu bekerja pada akhir pekan atau hari libur sesuai jadwal pameran
Bersedia dan siap ditempatkan di seluruh jaringan cabang perusahaan
Sales Counter
Wanita, tertarik dan menyukai dunia otomotif
Komunikatif dan dapat bekerja secara individu maupun tim
Berorientasi pada target dan hasil penjualan
Jujur, disiplin, dan bertanggung jawab
Memiliki SIM C aktif
Mekanik Motor
Laki-laki
Pengalaman minimal 1 tahun
Menyukai dunia otomotif
Pendidikan minimal SMA/SMK
Kirim Lamaran
Formulir:
https://forms.gle/N6mfqUbVnC2JF68y6
Email:
hrdthebikershop@gmail.com
No. Telepon:
+6285738325536`;

const TEST_LINK = 'https://www.threads.com/@andre.patra/post/Db8RPMwiZuD';

const TEST_SCAM = `Dibutuhkan Admin Online WFH
Gaji 8-15 juta/bulan
Syarat: min SMA, punya HP Android
Hubungi: 0812-3456-7890 (Budi - HRD PT Sukses Mandiri)
Langsung kerja, tidak perlu pengalaman
Kirim foto dan KTP sekarang ke WhatsApp
Transfer biaya pendaftaran Rp 500.000 ke rekening BCA 1234567890`;

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForAnalysis(page, timeout = 180000) {
  console.log('  Waiting for analysis to complete...');
  try {
    // Wait for result page or verdict badge - longer timeout for full pipeline
    await page.waitForSelector('[class*="verdict"], [class*="result"], [class*="VerdictBadge"], [data-testid*="verdict"], text=/AMAN|WASPADA|BAHAYA/i', { timeout: 300000 });
    console.log('  Analysis complete!');
    await delay(3000); // Extra time for UI to fully render
    return true;
  } catch (e) {
    console.log('  Timeout after 5 minutes, taking screenshot anyway...');
    return false;
  }
}

async function takeFullPageScreenshot(page, filename) {
  await page.screenshot({ path: path.join(IMAGES_DIR, filename), fullPage: true });
  console.log(`  Screenshot saved: ${filename}`);
}

async function testTextChannel(page) {
  console.log('\n=== Testing TEXT channel (The Biker Shop) ===');
  
  // Navigate to home/analyze page
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await delay(2000);
  
  // Screenshot the input form
  await takeFullPageScreenshot(page, 'tes text.png');
  
  // Find and fill the text input
  const textInput = await page.$('textarea, [contenteditable], input[type="text"]');
  if (textInput) {
    await textInput.fill(TEST_TEXT);
    console.log('  Text input filled');
  } else {
    console.log('  ERROR: Could not find text input');
    return;
  }
  
  // Find and click the submit button
  const submitBtn = await page.$('button[type="submit"], button:has-text("Verifikasi"), button:has-text("Analisis"), button:has-text("Submit"), button:has-text("Cek")');
  if (submitBtn) {
    // Screenshot the loading modal
    await submitBtn.click();
    await delay(3000);
    await takeFullPageScreenshot(page, 'mockup-loading.png');
    
    // Wait for analysis to complete
    await waitForAnalysis(page);
    await delay(2000);
    
    // Screenshot result - part 1 (top of page)
    await page.evaluate(() => window.scrollTo(0, 0));
    await delay(500);
    await takeFullPageScreenshot(page, 'hasil text 1.png');
    
    // Screenshot result - part 2 (scroll down for more details)
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
    await delay(500);
    await takeFullPageScreenshot(page, 'hasil text 2.png');
  } else {
    console.log('  ERROR: Could not find submit button');
  }
}

async function testImageChannel(page) {
  console.log('\n=== Testing IMAGE/OCR channel (VinFast) ===');
  
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await delay(2000);
  
  // Look for image/file input tab
  const imageTab = await page.$('button:has-text("Gambar"), button:has-text("Image"), button:has-text("Foto"), [data-tab*="image"], [data-tab*="gambar"]');
  if (imageTab) {
    await imageTab.click();
    await delay(1000);
  }
  
  // Screenshot the image input form
  await takeFullPageScreenshot(page, 'tes gambar.png');
  
  // Find file input and upload the OCR test image
  const ocrImagePath = path.join(__dirname, '../../ocr.webp');
  if (!fs.existsSync(ocrImagePath)) {
    console.log('  WARNING: ocr.webp not found, skipping image upload test');
    return;
  }
  
  const fileInput = await page.$('input[type="file"]');
  if (fileInput) {
    await fileInput.setInputFiles(ocrImagePath);
    console.log('  Image uploaded');
    await delay(2000);
    
    // Find and click submit
    const submitBtn = await page.$('button[type="submit"], button:has-text("Verifikasi"), button:has-text("Analisis"), button:has-text("Submit"), button:has-text("Cek")');
    if (submitBtn) {
      await submitBtn.click();
      await waitForAnalysis(page);
      await delay(2000);
      
      await page.evaluate(() => window.scrollTo(0, 0));
      await delay(500);
      await takeFullPageScreenshot(page, 'hasil gambar 1.png');
      
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
      await delay(500);
      await takeFullPageScreenshot(page, 'hasil gambar 2.png');
    }
  } else {
    console.log('  ERROR: Could not find file input');
  }
}

async function testLinkChannel(page) {
  console.log('\n=== Testing LINK/URL channel (SISI) ===');
  
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await delay(2000);
  
  // Look for URL/link tab
  const linkTab = await page.$('button:has-text("Link"), button:has-text("URL"), button:has-text("Tautan"), [data-tab*="link"], [data-tab*="url"]');
  if (linkTab) {
    await linkTab.click();
    await delay(1000);
  }
  
  // Screenshot the link input form
  await takeFullPageScreenshot(page, 'tes link.png');
  
  // Find and fill URL input
  const urlInput = await page.$('input[type="url"], input[placeholder*="http"], input[placeholder*="URL"], input[placeholder*="link"], input[placeholder*="tautan"], textarea');
  if (urlInput) {
    await urlInput.fill(TEST_LINK);
    console.log('  URL input filled');
  } else {
    console.log('  ERROR: Could not find URL input');
    return;
  }
  
  // Find and click submit
  const submitBtn = await page.$('button[type="submit"], button:has-text("Verifikasi"), button:has-text("Analisis"), button:has-text("Submit"), button:has-text("Cek")');
  if (submitBtn) {
    await submitBtn.click();
    await waitForAnalysis(page);
    await delay(2000);
    
    await page.evaluate(() => window.scrollTo(0, 0));
    await delay(500);
    await takeFullPageScreenshot(page, 'hasil link 1.png');
    
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
    await delay(500);
    await takeFullPageScreenshot(page, 'hasil link 2.png');
  }
}

async function testNegativeCase(page) {
  console.log('\n=== Testing NEGATIVE case (Scam - BAHAYA) ===');
  
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await delay(2000);
  
  // Fill with scam text
  const textInput = await page.$('textarea, [contenteditable], input[type="text"]');
  if (textInput) {
    await textInput.fill(TEST_SCAM);
    console.log('  Scam text filled');
  }
  
  const submitBtn = await page.$('button[type="submit"], button:has-text("Verifikasi"), button:has-text("Analisis"), button:has-text("Submit"), button:has-text("Cek")');
  if (submitBtn) {
    await submitBtn.click();
    await waitForAnalysis(page);
    await delay(2000);
    
    await page.evaluate(() => window.scrollTo(0, 0));
    await delay(500);
    await takeFullPageScreenshot(page, 'hasil test negatif.png');
  }
}

async function testCommunityAndHistory(page) {
  console.log('\n=== Testing Community & History pages ===');
  
  // Community page
  await page.goto(`${BASE_URL}/community`, { waitUntil: 'networkidle' });
  await delay(2000);
  await takeFullPageScreenshot(page, 'mockup-community.png');
  
  // History/Riwayat page
  await page.goto(`${BASE_URL}/history`, { waitUntil: 'networkidle' });
  await delay(2000);
  await takeFullPageScreenshot(page, 'mockup-riwayat.png');
  
  // Try alternative paths
  try {
    await page.goto(`${BASE_URL}/riwayat`, { waitUntil: 'networkidle', timeout: 5000 });
    await delay(1000);
    await takeFullPageScreenshot(page, 'mockup-riwayat.png');
  } catch (e) {
    // /history already captured
  }
}

async function main() {
  console.log('Starting Verifin E2E Test Suite...');
  console.log(`Images will be saved to: ${IMAGES_DIR}`);
  
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: 'id-ID'
  });
  const page = await context.newPage();
  
  try {
    // Test 1: Text channel
    await testTextChannel(page);
    
    // Test 2: Image/OCR channel
    await testImageChannel(page);
    
    // Test 3: Link channel
    await testLinkChannel(page);
    
    // Test 4: Negative case (scam)
    await testNegativeCase(page);
    
    // Test 5: Community & History
    await testCommunityAndHistory(page);
    
    console.log('\n=== ALL TESTS COMPLETE ===');
  } catch (error) {
    console.error('Test failed:', error.message);
    // Take error screenshot
    await page.screenshot({ path: path.join(IMAGES_DIR, 'error-debug.png'), fullPage: true });
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
