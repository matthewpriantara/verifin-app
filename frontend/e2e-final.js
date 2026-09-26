const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const IMAGES_DIR = path.join(__dirname, '../../proposal-verifin/images');
const BASE_URL = 'http://localhost:3000';
const TEST_LINK = 'https://www.threads.com/@andre.patra/post/Db8RPMwiZuD';

async function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

async function waitForResult(page, timeoutMs = 300000) {
  console.log('  Polling for verdict...');
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      // Look for the result page URL pattern or verdict-specific elements
      const url = page.url();
      if (url.includes('/result') || url.includes('/hasil') || url.includes('/verify')) {
        console.log(`  Result page detected: ${url}`);
        await delay(3000);
        return true;
      }
      
      // Look for verdict badge elements (not page text)
      const verdict = await page.$('[class*="verdict-badge"], [class*="VerdictBadge"], [class*="risk-score"], [class*="RiskScore"]');
      if (verdict) {
        const text = await verdict.textContent();
        console.log(`  Verdict element found: ${text}`);
        await delay(3000);
        return true;
      }
      
      // Check if loading modal is gone
      const loadingModal = await page.$('[class*="modal"], [class*="loading"], [class*="progress"]');
      if (!loadingModal) {
        // Modal gone, check for result content
        const resultContent = await page.$('text=/Faktor Penilaian|Rekomendasi Sebelum|Perusahaan & Lokasi/i');
        if (resultContent) {
          console.log('  Result content detected');
          await delay(3000);
          return true;
        }
      }
    } catch (e) {}
    await delay(5000);
    const elapsed = Math.round((Date.now() - start) / 1000);
    if (elapsed % 15 === 0) process.stdout.write(`  ${elapsed}s...`);
  }
  console.log('\n  Timeout!');
  return false;
}

async function screenshot(page, filename) {
  await page.screenshot({ path: path.join(IMAGES_DIR, filename), fullPage: true });
  console.log(`  Saved: ${filename}`);
}

async function main() {
  console.log('=== Verifin Screenshot Test (Final) ===');
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'id-ID' });
  const page = await ctx.newPage();

  try {
    // ========== OCR/IMAGE TEST ==========
    console.log('\n--- IMAGE/OCR Test (VinFast) ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(3000);

    await screenshot(page, 'tes gambar.png');

    const ocrPath = path.join(__dirname, '../../ocr.webp');
    if (fs.existsSync(ocrPath)) {
      // Find file input (may be hidden, triggered by "Lampirkan gambar" button)
      const fileInput = await page.$('input[type="file"]');
      if (fileInput) {
        await fileInput.setInputFiles(ocrPath);
        console.log('  Image uploaded');
        await delay(2000);

        const btn = await page.$('button:has-text("Verifikasi")');
        if (btn) {
          await btn.click({ force: true });
          await waitForResult(page);
          await page.evaluate(() => window.scrollTo(0, 0));
          await delay(500);
          await screenshot(page, 'hasil gambar 1.png');
          await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
          await delay(500);
          await screenshot(page, 'hasil gambar 2.png');
        } else {
          console.log('  ERROR: Verifikasi button not found');
        }
      } else {
        console.log('  ERROR: File input not found');
      }
    } else {
      console.log('  ocr.webp not found, skipping');
    }

    // ========== LINK TEST ==========
    console.log('\n--- LINK/URL Test (SISI) ---');
    // Navigate fresh to reset form state
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(3000);

    await screenshot(page, 'tes link.png');

    // The frontend uses a single textarea for text/URL input
    const urlInput = await page.$('textarea');
    if (urlInput) {
      await urlInput.fill(TEST_LINK);
      console.log('  URL filled');
      await delay(1000);
    }

    // Click Verifikasi button
    const btn2 = await page.$('button:has-text("Verifikasi")');
    if (btn2) {
      await btn2.click({ force: true });
      await waitForResult(page);
      await page.evaluate(() => window.scrollTo(0, 0));
      await delay(500);
      await screenshot(page, 'hasil link 1.png');
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
      await delay(500);
      await screenshot(page, 'hasil link 2.png');
    } else {
      console.log('  ERROR: Verifikasi button not found');
    }

    console.log('\n=== DONE ===');
  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: path.join(IMAGES_DIR, 'error-debug.png'), fullPage: true });
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
