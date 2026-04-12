import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const CONFIG_PATH = './config.json';
const DATA_DIR = './data';

async function scrape() {
  const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));

  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const now = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

  for (const product of config.products) {
    console.log(`Scraping: ${product.name} (${product.site})`);
    console.log(`  URL: ${product.url}`);

    try {
      const page = await browser.newPage();
      await page.setUserAgent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      );
      await page.goto(product.url, { waitUntil: 'networkidle2', timeout: 30000 });

      // Try each selector (comma-separated) until one works
      const selectors = product.selector.split(',').map(s => s.trim());
      let priceText = null;

      for (const sel of selectors) {
        try {
          await page.waitForSelector(sel, { timeout: 5000 });
          priceText = await page.$eval(sel, el => el.textContent.trim());
          if (priceText) {
            console.log(`  Matched selector: ${sel}`);
            break;
          }
        } catch {
          // selector not found, try next
        }
      }

      if (!priceText) {
        // Fallback: look for any element containing a dollar amount on the page
        priceText = await page.evaluate(() => {
          const elements = document.querySelectorAll('*');
          for (const el of elements) {
            if (el.children.length === 0) {
              const text = el.textContent.trim();
              if (/^\$[\d,]+(\.\d{2})?$/.test(text)) {
                return text;
              }
            }
          }
          return null;
        });
        if (priceText) console.log(`  Found price via fallback scan`);
      }

      await page.close();

      if (!priceText) {
        console.log(`  WARNING: No price found for ${product.name}`);
        continue;
      }

      // Clean price: "$1,299.99" -> 1299.99
      const price = parseFloat(priceText.replace(/[^0-9.]/g, ''));
      if (isNaN(price)) {
        console.log(`  WARNING: Could not parse price "${priceText}"`);
        continue;
      }

      console.log(`  Price: $${price}`);

      // Load or create data file
      const dataFile = path.join(DATA_DIR, `${product.id}.json`);
      let data = { id: product.id, name: product.name, url: product.url, site: product.site, history: [] };

      if (fs.existsSync(dataFile)) {
        data = JSON.parse(fs.readFileSync(dataFile, 'utf-8'));
        // Update name/url/site in case config changed
        data.name = product.name;
        data.url = product.url;
        data.site = product.site;
      }

      // Only add if we don't already have today's price
      const lastEntry = data.history[data.history.length - 1];
      if (lastEntry && lastEntry.date === now) {
        console.log(`  Already have today's price, updating...`);
        lastEntry.price = price;
      } else {
        data.history.push({ date: now, price });
      }

      fs.writeFileSync(dataFile, JSON.stringify(data, null, 2));
      console.log(`  Saved to ${dataFile}`);

    } catch (err) {
      console.error(`  ERROR scraping ${product.name}: ${err.message}`);
    }
  }

  await browser.close();
  console.log('\nDone.');
}

scrape();
