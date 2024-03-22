# Use the specified base image
FROM ubuntu:jammy

# Add a new user with the same user ID and group ID from the host machine
ARG USER
ARG USER_ID
ARG GROUP
ARG GROUP_ID
RUN groupadd -g $GROUP_ID $GROUP && \
    adduser --uid $USER_ID --ingroup $GROUP $USER

# Install necessary software
ENV TZ="America/Los_Angeles"
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y \
    llvm-dev \
    fish \
    vim \
    tmux \
    sudo \
    default-jdk \
    clang \
    lld \
    cmake \
    ninja-build \
    git \
    python3-pip \
    fuse3 \
    curl \
    autoconf \
    libtool \
    ripgrep \
    wget \
    neovim \
    lldb \
    golang \
    gdu \
    python3.10-venv \
    pv \
    pipx \
    rsync \
    rclone \
    ccache

# Install Mull
RUN curl -L -o Mull.deb 'https://github.com/mull-project/mull/releases/download/0.21.1/Mull-14-0.21.1-LLVM-14.0-ubuntu-22.04.deb' \
    && apt install ./Mull.deb \
    && rm Mull.deb

# Install rclone
RUN curl -L -o rclone.deb 'https://downloads.rclone.org/v1.64.0/rclone-v1.64.0-linux-amd64.deb' \
    && apt install ./rclone.deb \
    && rm rclone.deb

# Install protobuf
ARG PROTOBUF_VERSION=3.20.3
RUN git clone -b v${PROTOBUF_VERSION} --recursive https://github.com/protocolbuffers/protobuf.git \
    && cd protobuf && ./autogen.sh \
    && ./configure --enable-static=no \
    && make -j${NPROC} install && ldconfig \
    && cd python && python3 setup.py install --cpp_implementation \
    && cd ../.. && rm -rf protobuf

# Install bazel
RUN wget -O /usr/bin/bazel https://github.com/bazelbuild/bazelisk/releases/download/v1.19.0/bazelisk-linux-amd64 && \
    chmod +x /usr/bin/bazel

# Give the current user sudo rights
ARG USER
RUN echo "$USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER && \
    chmod 0440 /etc/sudoers.d/$USER
    
# Switch to the given user
ARG USER
USER $USER

# Install Conda based on https://github.com/conda-forge/miniforge-images/blob/master/ubuntu/DockerfileARG USER
ARG MINIFORGE_NAME=Miniforge3
ARG MINIFORGE_VERSION=23.3.1-1
ENV CONDA_DIR="/home/$USER/conda"
RUN wget --no-hsts --quiet \
    https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/${MINIFORGE_NAME}-${MINIFORGE_VERSION}-Linux-$(uname -m).sh -O /tmp/miniforge.sh && \
    /bin/bash /tmp/miniforge.sh -b -p ${CONDA_DIR} && \
    rm /tmp/miniforge.sh && \
    . ${CONDA_DIR}/etc/profile.d/conda.sh \
    conda clean --tarballs --index-cache --packages --yes && \
    find ${CONDA_DIR} -follow -type f -name '*.a' -delete && \
    find ${CONDA_DIR} -follow -type f -name '*.pyc' -delete && \
    conda clean --force-pkgs-dirs --all --yes  && \
    echo ". ${CONDA_DIR}/etc/profile.d/conda.sh && . ${CONDA_DIR}/etc/profile.d/mamba.sh" >> ~/.bashrc

# Create environment and install project
COPY mlirmut /mlirmut
ARG PY_DEPS="\
    python=3.12 \
    pip \
    onnx=1.15.0 \
    click=8.1.7 \
    pyyaml=6.0.1 \
    "
RUN . ${CONDA_DIR}/etc/profile.d/conda.sh && . ${CONDA_DIR}/etc/profile.d/mamba.sh \
    && mamba create -y -q -n synthfuzz ${PY_DEPS} \
    && mamba activate synthfuzz \
    && pip install -e /mlirmut \
    && echo "mamba activate synthfuzz" >> ~/.bashrc
