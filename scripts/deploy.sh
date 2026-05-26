#!/bin/bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <prod|dev>" >&2
  exit 1
fi

ENV="$1"

case "$ENV" in
  prod) BRANCH="main"    ;;
  dev)  BRANCH="develop" ;;
  *)
    echo "Invalid env: $ENV (must be prod or dev)" >&2
    exit 1
    ;;
esac

REPO_DIR="/opt/language-teacher/$ENV"
AWS_REGION="${AWS_REGION:-ap-northeast-1}"
PARAM_PREFIX="/language-teacher/$ENV"
export COMPOSE_PROJECT_NAME="lt-$ENV"

cd "$REPO_DIR"

echo "==> [$ENV] Pulling latest code from origin/$BRANCH..."
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

echo "==> [$ENV] Fetching secrets from SSM ($PARAM_PREFIX)..."
get_param() {
  aws ssm get-parameter \
    --name "$1" \
    --with-decryption \
    --query "Parameter.Value" \
    --output text \
    --region "$AWS_REGION"
}

GEMINI_API_KEY=$(get_param "$PARAM_PREFIX/gemini-api-key")
REPORT_CHANNEL_ID=$(get_param "$PARAM_PREFIX/report-channel-id")
QUIZ_CHANNEL_ID=$(get_param "$PARAM_PREFIX/quiz-channel-id")
EN_LEARNER_NAME=$(get_param "$PARAM_PREFIX/en-learner-name")
JA_LEARNER_NAME=$(get_param "$PARAM_PREFIX/ja-learner-name")
EN_LEARNER_DISCORD_ID=$(get_param "$PARAM_PREFIX/en-learner-discord-id")
JA_LEARNER_DISCORD_ID=$(get_param "$PARAM_PREFIX/ja-learner-discord-id")
DISCORD_BOT_TOKEN_EN=$(get_param "$PARAM_PREFIX/discord-bot-token-en")
DISCORD_BOT_TOKEN_JA=$(get_param "$PARAM_PREFIX/discord-bot-token-ja")

write_env_file() {
  local file="$1"
  local role="$2"
  local token="$3"
  umask 077
  cat > "$file" <<EOF
BOT_ROLE=$role
DISCORD_BOT_TOKEN=$token
GEMINI_API_KEY=$GEMINI_API_KEY
REPORT_CHANNEL_ID=$REPORT_CHANNEL_ID
QUIZ_CHANNEL_ID=$QUIZ_CHANNEL_ID
EN_LEARNER_NAME=$EN_LEARNER_NAME
EN_LEARNER_DISCORD_ID=$EN_LEARNER_DISCORD_ID
JA_LEARNER_NAME=$JA_LEARNER_NAME
JA_LEARNER_DISCORD_ID=$JA_LEARNER_DISCORD_ID
EOF
}

write_env_file ".env.en" "en_teacher" "$DISCORD_BOT_TOKEN_EN"
write_env_file ".env.ja" "ja_teacher" "$DISCORD_BOT_TOKEN_JA"

echo "==> [$ENV] Ensuring data directory exists with correct ownership..."
mkdir -p data
chown -R 1000:1000 data

echo "==> [$ENV] Building and starting containers (project: $COMPOSE_PROJECT_NAME)..."
docker compose up -d --build

echo "==> [$ENV] Recent logs:"
sleep 3
docker compose logs --tail=20 || true

echo "==> [$ENV] Deploy complete."
