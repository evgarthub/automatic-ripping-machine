#!/bin/bash
# This script is first to run due to this: https://github.com/phusion/baseimage-docker#running_startup_scripts.
#
# It updates the UIG or GID of the included arm user to whatever value the user
# passes at runtime, if the value set is not the default value of 1000
#
# If the container is run again without specifying UID and GID, this script
# resets the UID and GID of all files in ARM directories to the defaults

set -euo pipefail

export ARM_HOME="/home/arm"
DEFAULT_UID=1000
DEFAULT_GID=1000


# Function to check if the ARM user has ownership of the requested folder
check_folder_ownership() {
    local check_dir="$1"  # Get the folder path from the first argument
    local folder_uid=$(stat -c "%u" "$check_dir")
    local folder_gid=$(stat -c "%g" "$check_dir")

    echo "Checking ownership of $check_dir"

    if [ "$folder_uid" != "$ARM_UID" ] || [ "$folder_gid" != "$ARM_GID" ]; then
        if [[ "${ARM_DEV_MODE:-}" == "true" ]]; then
            echo "[WARN]: $check_dir is $folder_uid:$folder_gid (expected $ARM_UID:$ARM_GID); ARM_DEV_MODE=true — continuing."
            return 0
        fi
        echo "---------------------------------------------"
        echo "[ERROR]: ARM does not have permissions to $check_dir using $ARM_UID:$ARM_GID"
        echo "Check your user permissions and restart ARM. Folder permissions--> $folder_uid:$folder_gid"
        echo "---------------------------------------------"
        exit 1
    fi

    echo "[OK]: ARM UID and GID set correctly, ARM has access to '$check_dir' using $ARM_UID:$ARM_GID"
}

### Setup User
if [[ $ARM_UID -ne $DEFAULT_UID ]]; then
  echo -e "Updating arm user id from $DEFAULT_UID to $ARM_UID..."
  usermod -u "$ARM_UID" arm
elif [[ $ARM_UID -eq $DEFAULT_UID ]]; then
  echo -e "Updating arm group id $ARM_UID to default (1000)..."
  usermod -u $DEFAULT_UID arm
fi

if [[ $ARM_GID -ne $DEFAULT_GID ]]; then
  echo -e "Updating arm group id from $DEFAULT_GID to $ARM_GID..."
  groupmod -og "$ARM_GID" arm
elif [[ $ARM_GID -eq $DEFAULT_GID ]]; then
  echo -e "Updating arm group id $ARM_GID to default (1000)..."
  groupmod -og $DEFAULT_GID arm
fi
echo "Adding arm user to 'render' group"
if ! getent group render > /dev/null 2>&1; then
  # The render group doesn't exist inside the container. Create it with the
  # host GID when the device is passed through so /dev/dri stays accessible,
  # otherwise fall back to a new group.
  if [ -e /dev/dri/renderD128 ]; then
    RENDER_GID=$(stat -c "%g" /dev/dri/renderD128)
  else
    RENDER_GID=""
  fi
  if [ -n "$RENDER_GID" ] && ! getent group "$RENDER_GID" > /dev/null 2>&1; then
    groupadd -g "$RENDER_GID" render
  else
    groupadd render
  fi
fi
usermod -a -G render arm

### Setup Files
if [[ "${ARM_FORCE_CHOWN:-}" == "true" ]]; then
  echo "ARM_FORCE_CHOWN=true - forcing recursive chown of /opt/arm (including mounted paths)..."
  chown -R arm:arm /opt/arm
  echo "Forced chown of /opt/arm complete"
else
  ARM_TREE_OWNER=$(stat -c "%u:%g" /opt/arm)
  if [ "$ARM_TREE_OWNER" != "$(id -u arm):$(id -g arm)" ]; then
    echo "Fixing ownership of /opt/arm (${ARM_TREE_OWNER} -> arm:arm), skipping mounted paths..."
    find /opt/arm -xdev -print0 | xargs -0 -r chown arm:arm
    echo "Ownership of /opt/arm updated"
  else
    echo "/opt/arm already owned by arm - skipping recursive chown"
  fi
fi

# Ensure ownership of mounted dirs
# Create the config dir first - without a bind mount /etc/arm/config does not
# exist yet and the chown below would abort the startup script (set -e)
mkdir -p /etc/arm/config
chown arm:arm /home/arm
chown arm:arm /etc/arm/config

# Check ownership of the ARM home folder
check_folder_ownership "/home/arm"

# setup needed/expected dirs if not found
SUBDIRS="media media/completed media/raw media/movies media/transcode logs logs/progress db music .MakeMKV"
for dir in $SUBDIRS ; do
  thisDir="$ARM_HOME/$dir"
  if [[ ! -d "$thisDir" ]] ; then
    echo "Creating dir: $thisDir"
    mkdir -p "$thisDir"
    # Set the default ownership to arm instead of root
    chown -R arm:arm "$thisDir"
  fi
done

echo "Removing any link between music and Music"
if [ -h /home/arm/Music ]; then
  echo "Music symbolic link found, removing link"
  unlink /home/arm/Music
fi

##### Setup ARM-specific config files if not found
# Check ownership of the ARM config folder
check_folder_ownership "/etc/arm/config"

mkdir -p /etc/arm/config
CONFS="arm.yaml apprise.yaml"
for conf in $CONFS; do
  thisConf="/etc/arm/config/${conf}"
  if [[ ! -f "${thisConf}" ]] ; then
    echo "Config not found! Creating config file: ${thisConf}"
    # Don't overwrite with defaults during reinstall
    cp --no-clobber "/opt/arm/setup/${conf}" "${thisConf}"
  fi
done

# Config files copied above are created as root, and files bind-mounted from
# the host may be owned by another user. The armui runs as the arm user and
# needs write access to update the configs from the settings pages.
chown -R arm:arm /etc/arm/config

##### abcde config setup
# abcde.conf is expected in /etc by the abcde installation
echo "Checking location of abcde configuration files"
# Test if abcde.conf is a hyperlink, if so remove it
if [ -h /etc/arm/config/abcde.conf ]; then
  echo "Old hyper link exists removing!"
  unlink /etc/arm/config/abcde.conf
fi
# check if abcde is in config main location - only copy if it doesnt exist
if ! [ -f /etc/arm/config/abcde.conf ]; then
  echo "abcde.conf doesnt exist"
  cp /opt/arm/setup/.abcde.conf /etc/arm/config/abcde.conf
  chown arm:arm /etc/arm/config/abcde.conf
fi
# The system link to the fake default file -not really needed but as a precaution to the -C variable being blank
if ! [ -h /etc/abcde.conf ]; then
  echo "/etc/abcde.conf link doesnt exist"
  ln -sf /etc/arm/config/abcde.conf /etc/abcde.conf
fi

# symlink $ARM_HOME/Music to $ARM_HOME/music because the config for abcde doesn't match the docker compose docs
# separate rm and ln commands because "ln -sf" does the wrong thing if dest is a symlink to a directory
# rm -rf $ARM_HOME/music
# ln -s $ARM_HOME/Music $ARM_HOME/music

# Setup Timezone info
echo "Setting ARM Timezone info: $TZ"
DEBIAN_FRONTEND=noninteractive
ln -sf /usr/share/zoneinfo/$TZ /etc/localtime
dpkg-reconfigure --frontend noninteractive tzdata