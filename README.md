# GPIPS India Opportunity Intelligence Demo

Streamlit POC for the GPIPS India market demo.

The demo shows a guided flow:

```text
Data Layer -> Knowledge Layer -> Insight Engine -> Opportunity Pool -> Recommendation
```

It reads the provided ZIP file locally:

```text
/Users/sjmizhangjingjing/Downloads/GPIPS系统数据库与知识库.zip
```

## Run

```bash
cd gpips-india-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open:

```text
http://127.0.0.1:8501
```

## Data

By default, the app reads:

```text
/Users/sjmizhangjingjing/Downloads/GPIPS系统数据库与知识库.zip
```

If another machine runs the demo, put the ZIP anywhere locally and update the `Source zip` field in the Streamlit sidebar.

## Demo Story

The recommended guided demo question is:

> In India 15K-20K INR, for T2/T3 young replacement buyers, what opportunity can GPIPS discover from market data, product ratings, user comments, and knowledge reports?

The primary generated opportunity is:

```text
15K-20K INR compact + durable + large-battery 5G phone
```

## Notes

- The app uses built-in XML parsing for `.xlsx` and `.docx`, so it does not require `openpyxl`.
- Rating data is treated as India Flipkart product rating data.
- Review data is filtered to `country_alpha2 = IN` for the main demo.
- Non-India reviews can be treated as future multi-market voice-of-user expansion data.

## Suggested GitHub Upload

Do not commit the source ZIP unless the data is approved for repository storage.

```bash
git init
git add .
git commit -m "Add GPIPS India Streamlit demo"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```
