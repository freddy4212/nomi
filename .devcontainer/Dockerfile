FROM --platform=linux/arm64 ubuntu:25.10

ENV DEBIAN_FRONTEND=noninteractive

# Install required packages
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
	build-essential sudo git nano wget xz-utils ca-certificates \
	&& rm -rf /var/lib/apt/lists/*

# Allow build-time override of username/uid/gid so host <-> container ownership can match
ARG USERNAME=freddy
ARG USER_UID=501
ARG USER_GID=20

# Create group (use 'dialout' name to match common host group for serial access) and user
# If the group or user already exists, commands will not fail the build
RUN set -eux; \
	groupadd -g "${USER_GID}" dialout 2>/dev/null || true; \
	if id -u "${USERNAME}" >/dev/null 2>&1; then \
		echo "user ${USERNAME} already exists"; \
	else \
		# try to create with UID if provided; if that fails/falls through create without -u
		if [ -n "${USER_UID}" ]; then \
			useradd -m -s /bin/bash -u "${USER_UID}" -g "${USER_GID}" "${USERNAME}" 2>/dev/null || useradd -m -s /bin/bash -g "${USER_GID}" "${USERNAME}"; \
		else \
			useradd -m -s /bin/bash -g "${USER_GID}" "${USERNAME}"; \
		fi; \
	fi; \
	# ensure sudo and passwordless sudo for the user
	apt-get update && apt-get install -y --no-install-recommends sudo && rm -rf /var/lib/apt/lists/*; \
	echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME}; \
	chmod 0440 /etc/sudoers.d/${USERNAME}

# Prepare workspace directory
RUN mkdir -p /workspace \
	&& chown ${USERNAME}:dialout /workspace || true

ENV HOME=/home/freddy
USER ${USERNAME}
WORKDIR /workspace

# Run post-create actions at image build: download toolchain, clone repo, set env and permissions
USER root
RUN set -e; \
	TOOL_URL="https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-aarch64-arm-none-eabi.tar.xz"; \
	UTILS_DIR="/home/freddy/utils"; \
	TC_DIR="$UTILS_DIR/arm-gnu-toolchain-13.3.rel1-aarch64-arm-none-eabi"; \
	REPO_DIR="$UTILS_DIR/Seeed_Grove_Vision_AI_Module_V2"; \
	mkdir -p "$UTILS_DIR"; \
	echo "=== Starting toolchain and repo setup ==="; \
	# Download toolchain if not present
	if [ ! -d "$TC_DIR" ]; then \
		tmpfile="/tmp/arm-toolchain.tar.xz"; \
		echo "Downloading ARM toolchain from $TOOL_URL ..."; \
		if wget --tries=3 --timeout=60 --waitretry=10 -O "$tmpfile" "$TOOL_URL"; then \
			echo "Download successful, extracting to $UTILS_DIR..."; \
			tar -xJf "$tmpfile" -C "$UTILS_DIR" && echo "Toolchain extracted successfully"; \
			rm -f "$tmpfile"; \
		else \
			echo "WARNING: Toolchain download failed, skipping (container will still build)"; \
			rm -f "$tmpfile" || true; \
		fi; \
	else \
		echo "Toolchain already exists at $TC_DIR"; \
	fi; \
	# Clone repo if not present
	if [ ! -d "$REPO_DIR" ]; then \
		echo "Cloning Seeed repo..."; \
		if git clone --depth=1 https://github.com/HimaxWiseEyePlus/Seeed_Grove_Vision_AI_Module_V2.git "$REPO_DIR"; then \
			echo "Repository cloned successfully"; \
		else \
			echo "WARNING: Git clone failed, skipping (container will still build)"; \
		fi; \
	else \
		echo "Repository already exists at $REPO_DIR"; \
	fi; \
	# Ensure ownership of /home/${USERNAME} and utils (use configured group 'dialout')
	chown -R "${USERNAME}:dialout" "/home/${USERNAME}" 2>/dev/null || true; \
	# Create environment file for login shells
	mkdir -p /etc/profile.d; \
	printf '%s\n' "export PATH=\"$TC_DIR/bin:\$PATH\"" "export WE2_SDK_PATH=\"$REPO_DIR/EPII_CM55M_APP_S\"" > /etc/profile.d/we2_sdk.sh; \
	chmod 0644 /etc/profile.d/we2_sdk.sh; \
	echo "=== Setup completed ==="; \
	true
USER freddy

# Add runtime ENV so processes see toolchain and WE2_SDK_PATH
ENV PATH="/home/freddy/utils/arm-gnu-toolchain-13.3.rel1-aarch64-arm-none-eabi/bin:${PATH}"
ENV WE2_SDK_PATH="/home/freddy/utils/Seeed_Grove_Vision_AI_Module_V2/EPII_CM55M_APP_S"
