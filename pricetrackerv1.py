import streamlit as st
import pandas as pd
import playwright.async_api
import asyncio
import json
from datetime import datetime
import plotly.express as px
import sqlite3
from pathlib import Path

# Initialize database
def init_db():
    conn = sqlite3.connect('price_tracker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (url TEXT PRIMARY KEY, name TEXT, target_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS price_history
                 (url TEXT, price REAL, timestamp DATETIME,
                  FOREIGN KEY(url) REFERENCES products(url))''')
    conn.commit()
    conn.close()

# Scraper class
class AmazonScraper:
    def __init__(self, auth_path="auth.json"):
        with open(auth_path) as f:
            self.auth = json.load(f)
        
    async def get_price(self, url):
        playwright = await playwright.async_api.async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(
            f"wss://{self.auth['username']}:{self.auth['password']}@brd.superproxy.io:9222"
        )
        
        try:
            page = await browser.new_page()
            await page.goto(url)
            price_element = await page.wait_for_selector('.a-price-whole')
            price = await price_element.text_content()
            title_element = await page.wait_for_selector('#productTitle')
            title = await title_element.text_content()
            return float(price.replace(',', '')), title.strip()
        finally:
            await browser.close()
            await playwright.stop()

# Database operations
def add_product(url, name, target_price):
    conn = sqlite3.connect('price_tracker.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO products VALUES (?, ?, ?)",
              (url, name, target_price))
    conn.commit()
    conn.close()

def add_price_history(url, price):
    conn = sqlite3.connect('price_tracker.db')
    c = conn.cursor()
    c.execute("INSERT INTO price_history VALUES (?, ?, ?)",
              (url, price, datetime.now()))
    conn.commit()
    conn.close()

def get_all_products():
    conn = sqlite3.connect('price_tracker.db')
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

def get_price_history(url):
    conn = sqlite3.connect('price_tracker.db')
    df = pd.read_sql_query(
        "SELECT * FROM price_history WHERE url=? ORDER BY timestamp",
        conn, params=(url,))
    conn.close()
    return df

# Streamlit UI
st.title("Amazon Price Tracker")

# Initialize database
init_db()

# Sidebar for adding new products
with st.sidebar:
    st.header("Add New Product")
    new_url = st.text_input("Amazon.ca URL")
    target_price = st.number_input("Target Price", min_value=0.0, step=0.01)
    
    if st.button("Add Product"):
        try:
            scraper = AmazonScraper()
            price, name = asyncio.run(scraper.get_price(new_url))
            add_product(new_url, name, target_price)
            add_price_history(new_url, price)
            st.success("Product added successfully!")
        except Exception as e:
            st.error(f"Error adding product: {str(e)}")

# Main content area
st.header("Tracked Products")
products_df = get_all_products()

if not products_df.empty:
    for _, product in products_df.iterrows():
        st.subheader(product['name'])
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"Target Price: ${product['target_price']:.2f}")
            if st.button("Update Price", key=product['url']):
                try:
                    scraper = AmazonScraper()
                    price, _ = asyncio.run(scraper.get_price(product['url']))
                    add_price_history(product['url'], price)
                    st.success(f"Current Price: ${price:.2f}")
                except Exception as e:
                    st.error(f"Error updating price: {str(e)}")
        
        with col2:
            history_df = get_price_history(product['url'])
            if not history_df.empty:
                fig = px.line(history_df, x='timestamp', y='price',
                            title='Price History')
                st.plotly_chart(fig)
else:
    st.info("No products are being tracked. Add a product using the sidebar!")

# Requirements.txt content as a string
requirements = """
streamlit==1.31.0
pandas==2.2.0
playwright==1.41.0
plotly==5.18.0
"""

# Save requirements
Path("requirements.txt").write_text(requirements)
