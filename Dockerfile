FROM python:3.14

WORKDIR /app

# FIRST install CPU-only PyTorch (smaller and faster)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# THEN install the remaining dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]