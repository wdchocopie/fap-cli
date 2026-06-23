# Dockerfile — chạy 1 lượt FAP rồi thoát · run one FAP pass then exit.
# Build TỪ GỐC REPO · build FROM THE REPO ROOT:
#   docker build -f deploy/Dockerfile -t fapc .
# Bí mật KHÔNG bake vào image — mount lúc chạy (xem deploy/docker-run.sh).
# Secrets are NOT baked in — mount them at run time (see deploy/docker-run.sh).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUTF8=1 PIP_NO_CACHE_DIR=1

# Chỉ copy thứ cần để cài gói (không copy .env/output/credentials.json).
# Copy only what's needed to install the package (no secrets/PII).
COPY pyproject.toml requirements.txt requirements-gcal.txt README.md ./
COPY fapc ./fapc
RUN pip install -e ".[gcal]"

# Lịch chạy 1 lượt rồi thoát · one pass then exit. refresh lỗi -> dừng (&&).
CMD ["sh", "-c", "fap refresh && fap calendar-sync && fap notify today"]
