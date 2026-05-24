#!/bin/bash
set -euo pipefail

REPO_DIR="/opt/language-teacher"
AWS_REGION="${AWS_REGION:-ap-northeast-1}"
PARAM_PREFIX="/language-teacher"

cd "$REPO_DIR"

echo "==> Pulling latest code..."
git fetch origin main
git reset --hard origin/main

echo "==> Fetching secrets from SSM Parameter Store..."
get_param() {
  aws ssm get-parameter \
    --name "$1" \
    --with-decryption \
    --query "Parameter.Value" \
    --output text \
    --region "$AWS_REGION"
}

umask 077
cat > .env <<EOF
DISCORD_BOT_TOKEN=$(get_param "$PARAM_PREFIX/discord-bot-token")
GEMINI_API_KEY=$(get_param "$PARAM_PREFIX/gemini-api-key")
REPORT_CHANNEL_ID=$(get_param "$PARAM_PREFIX/report-channel-id")
EN_LEARNER_NAME=$(get_param "$PARAM_PREFIX/en-learner-name")
JA_LEARNER_NAME=$(get_param "$PARAM_PREFIX/ja-learner-name")
EOF

echo "==> Ensuring data directory exists with correct ownership..."
mkdir -p data
chown -R 1000:1000 data

echo "==> Building and starting container..."
docker compose up -d --build

echo "==> Recent logs:"
sleep 3
docker compose logs --tail=20 || true

echo "==> Deploy complete."
