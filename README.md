# 📄 Document question answering template

A simple Streamlit app that answers questions about an uploaded document via OpenAI's GPT-3.5.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://document-question-answering-template.streamlit.app/)


### Setup

1. Create an environment using venv


   ```
   $ python -m venv .venv
   ```

2. Activate your environment

   ```
   $ source .venv/bin/activate
   ```

3. Run the Python interpreter and type the commands: (pretty sure this is needed for RecursiveCharacterTextSplitter in document_chunker.py)

   ```
   >>> import nltk
   >>> nltk.download('punkt')
   ```

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```
