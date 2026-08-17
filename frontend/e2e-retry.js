const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const IMAGES_DIR = path.join(__dirname, '../../proposal-verifin/images');
const BASE_URL = 'http://localhost:3000';

const TEST_LINK = 'https://www.threads.com/@andre.patra/post/Db8RPMwiZuD';

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForAnalysis(page, timeout = 300000) {
  console.log('  Waiting for analysis to complete (up to 5 min)...');
  try {
    await page.waitForSelector('text=/AMAN|WASPADA|BAHAYA/i', { timeout });
    console.log('  Analysis complete!');
    await delay(3000);
    return true;
  } catch (e) {
    console.log('  Timeout, taking screenshot anyway...');
    return false;
  }
}

async function takeFullPageScreenshot(page, filename) {
  await page.screenshot({ path: path.join(IMAGES_DIR, filename), fullPage: true });
  console.log(`  Screenshot saved: ${filename}`);
}

async function main() {
  console.log('Starting Verifin E2E Test (OCR + Link retry)...');
  
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: 'id-ID'
  });
  const page = await context.newPage();
  
  try {
    // Test OCR/Image channel
    console.log('\n=== Testing IMAGE/OCR channel (VinFast) ===');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(2000);
    
    // Look for image/file input tab
    const imageTab = await page.$('button:has-text("Gambar"), button:has-text("Image"), button:has-text("Foto"), [data-tab*="image"], [data-tab*="gambar"]');
    if (imageTab) {
      await imageTab.click();
      await delay(1000);
    }
    
    await takeFullPageScreenshot(page, 'tes gambar.png');
    
    const ocrImagePath = path.join(__dirname, '../../ocr.webp');
    if (fs.existsSync(ocrImagePath)) {
      const fileInput = await page.$('input[type="file"]');
      if (fileInput) {
        await fileInput.setInputFiles(ocrImagePath);
        console.log('  Image uploaded');
        await delay(2000);
        
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
      }
    } else {
      console.log('  ocr.webp not found, skipping');
    }
    
    // Test Link channel
    console.log('\n=== Testing LINK/URL channel (SISI) ===');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await delay(2000);
    
    const linkTab = await page.$('button:has-text("Link"), button:has-text("URL"), button:has-text("Tautan"), [data-tab*="link"], [data-tab*="url"]');
    if (linkTab) {
      await linkTab.click();
      await delay(1000);
    }
    
    await takeFullPageScreenshot(page, 'tes link.png');
    
    const urlInput = await page.$('input[type="url"], input[placeholder*="http"], input[placeholder*="URL"], input[placeholder*="link"], input[placeholder*="tautan"], textarea');
    if (urlInput) {
      await urlInput.fill(TEST_LINK);
      console.log('  URL input filled');
    }
    
    const submitBtn2 = await page.$('button[type="submit"], button:has-text("Verifikasi"), button:has-text("Analisis"), button:has-text("Submit"), button:has-text("Cek")');
    if (submitBtn2) {
      await submitBtn2.click();
      await waitForAnalysis(page);
      await delay(2000);
      
      await page.evaluate(() => window.scrollTo(0, 0));
      await delay(500);
      await takeFullPageScreenshot(page, 'hasil link 1.png');
      
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
      await delay(500);
      await takeFullPageScreenshot(page, 'hasil link 2.png');
    }
    
    console.log('\n=== TESTS COMPLETE ===');
  } catch (error) {
    console.error('Test failed:', error.message);
    await page.screenshot({ path: path.join(IMAGES_DIR, 'error-debug.png'), fullPage: true });
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
