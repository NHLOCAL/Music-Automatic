const { resolveAppVersion } = require("./electron/app-version.cjs");

const appVersion = resolveAppVersion();

module.exports = {
  appId: "com.musicautomatic.albumdeduplicator",
  productName: "Music Automatic",
  directories: {
    buildResources: "build",
    output: "desktop-dist",
  },
  files: [
    "dist/**/*",
    "electron/**/*",
    "package.json",
  ],
  extraResources: [
    {
      from: "../api",
      to: "backend-source/api",
    },
    {
      from: "../music_dup_lib",
      to: "backend-source/music_dup_lib",
    },
    {
      from: "../frontend/dist",
      to: "backend-source/frontend/dist",
    },
  ],
  extraMetadata: {
    version: appVersion,
  },
  win: {
    target: "nsis",
    icon: "build/icons/app-icon.ico",
  },
  nsis: {
    installerIcon: "build/icons/app-icon.ico",
    uninstallerIcon: "build/icons/app-icon.ico",
    installerHeaderIcon: "build/icons/app-icon.ico",
  },
  publish: [
    {
      provider: "github",
      owner: "NHLOCAL",
      repo: "Music-Automatic",
      tagNamePrefix: "album-deduplicator-v",
      releaseType: "release",
    },
  ],
  artifactName: "${productName}-${version}-setup-${arch}.${ext}",
};
