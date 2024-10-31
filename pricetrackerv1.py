import streamlit as st
import pandas as pd
import playwright.async_api
import asyncio
from datetime import datetime
import plotly.express as px

# Use Streamlit's secrets management instead of local auth.json
# Add to .streamlit/secrets.toml:
# bright_data_username = "your_username"
# bright_data_password = "your_password"

# Initialize session state for storing data
if 'products' not in st.session_state:
    st.session_state.products = pd.DataFrame(columns=['url', 'name', 'target_price'])
if 'price_history' not in st.session_state:
    st.session_state.price_history = pd.DataFrame(columns=['url', 'price', 'timestamp'])

# Scraper class
class AmazonScraper:
    async def get_price(self, url):
        playwright = await playwright.async_api.async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(
            f"wss://{st.secrets.bright_data_username}:{st.secrets.bright_data_password}@brd.superproxy.io:9222"
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

# Data operations
def add_product(url, name, target_price):
    new_product = pd.DataFrame({
        'url': [url],
        'name': [name],
        'target_price': [target_price]
    })
    st.session_state.products = pd.concat([st.session_state.products, new_product], ignore_index=True)

def add_price_history(url, price):
    new_price = pd.DataFrame({
        'url': [url],
        'price': [price],
        'timestamp': [datetime.now()]
    })
    st.session_state.price_history = pd.concat([st.session_state.price_history, new_price], ignore_index=True)

def get_price_history(url):
    return st.session_state.price_history[st.session_state.price_history['url'] == url].sort_values('timestamp')

# Streamlit UI
st.title("Amazon Price Tracker")

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

if not st.session_state.products.empty:
    for _, product in st.session_state.products.iterrows():
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
