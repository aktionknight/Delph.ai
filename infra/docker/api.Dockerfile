FROM python:3.12-slim
WORKDIR /workspace
COPY apps/api/requirements.txt /workspace/apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt
COPY apps/api/app /workspace/apps/api/app
COPY prompts /workspace/prompts
RUN useradd --create-home launchpad
USER launchpad
WORKDIR /workspace/apps/api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
