#!/bin/bash

if [ "$#" -lt 1 ]; then
   echo "Usage: \$0 <dirpath>..."
   exit 1
fi

. .env

VOLUMES=""
for arg in "$@"
do
  # Check if the argument contains a colon
  if [[ $arg == *":"* ]]; then
      # Split the argument into two parts
      IFS=':' read -r -a array <<< "$arg"
      HOST_DIR=${array[0]}
      TARGET_DIR=${array[1]}
      # Get the real path for the host directory
      DIRPATH=$(realpath "$HOST_DIR")
      # Prepare the bind-mount argument
      VOLUMES="$VOLUMES -v $DIRPATH:$TARGET_DIR"
  else
      # If there's no colon, treat it as a simple path
      DIRPATH=$(realpath "$arg")
      TARGET_DIR=$DIRPATH
      VOLUMES="$VOLUMES -v $DIRPATH:$TARGET_DIR"
  fi
done

USERNAME=$(whoami)
USER_ID=$(id -u)
GROUP_ID=$(id -g)
#    -v /etc/passwd:/etc/passwd:ro \
#    -v /etc/group:/etc/group:ro \
#    --device=/dev/fuse \
#    --security-opt apparmor:unconfined \
#    --cap-add SYS_ADMIN \

NEXT_CMD="docker run \
    --name $ENV_IMG_NAME \
    $VOLUMES \
    --workdir $TARGET_DIR \
    --user $USER_ID:$GROUP_ID \
    -it \
    -d \
    $ENV_IMG_NAME:$ENV_IMG_TAG"
echo "$NEXT_CMD"
$NEXT_CMD
