from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, AnyHttpUrl
from playwright.async_api import async_playwright
import openai
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# Configure OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

class Review(BaseModel):
    title: str
    body: str
    rating: int
    reviewer: str

class ReviewsResponse(BaseModel):
    reviews_count: int
    reviews: list[Review]

async def extract_reviews_from_page(page, url):
    # Navigate to URL
    await page.goto(url)
    html_content = await page.content()

    # Use OpenAI to identify CSS selectors
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=f"Analyze the following HTML and provide CSS selectors for reviews:\n{html_content}",
        max_tokens=500
    )
    selectors = json.loads(response.choices[0].text.strip())

    # Extract reviews
    reviews = []
    review_elements = await page.query_selector_all(selectors["review_container"])
    for element in review_elements:
        reviews.append(Review(
            title=await (await element.query_selector(selectors["title"])).inner_text(),
            body=await (await element.query_selector(selectors["body"])).inner_text(),
            rating=int(await (await element.query_selector(selectors["rating"])).inner_text()),
            reviewer=await (await element.query_selector(selectors["reviewer"])).inner_text(),
        ))
    return reviews

@app.get("/api/reviews", response_model=ReviewsResponse)
async def get_reviews(url: AnyHttpUrl = Query(..., description="Product page URL")):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            reviews = await extract_reviews_from_page(page, url)
            return ReviewsResponse(
                reviews_count=len(reviews),
                reviews=reviews
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            await browser.close()
