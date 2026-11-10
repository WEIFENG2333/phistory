# System Prompt

## Block 1

You are a helpful software engineer assistant.

# Messages

## Message 1 · user · text

Reply with one short sentence.

## Message 2 · user · text

Current runtime context. This snapshot supersedes earlier runtime-context snapshots.

Current working directory: "$PHISTORY_WORKSPACE".

# Tools

## bash

Run commands in a bash shell
* When invoking this tool, the contents of the "command" parameter does NOT need to be XML-escaped.
* Network access depends on the task environment. Prefer configured mirrors/proxies when they are available.
* State is persistent across command calls and discussions with the user.
* To inspect a particular line range of a file, e.g. lines 10-25, try 'sed -n 10,25p /path/to/the/file'.
* Please avoid commands that may produce a very large amount of output.
* Please run long lived commands in the background, e.g. 'sleep 10 &' or start a server in the background.

```json
{
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "description": "The bash command to run. Relative path is preferred in the command."
    }
  },
  "required": [
    "command"
  ]
}
```

## read_image

Read a PNG/JPEG/WebP/GIF file and return the image itself. Large images are downscaled automatically; do not install image libraries or create thumbnails to inspect an image.

```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "Path to the image file, resolved by the filesystem backend."
    }
  },
  "required": [
    "file_path"
  ]
}
```

## working_directory

Read the current working directory, or change it with cd. Relative paths use the current directory. Existing shells and running processes keep their own directories.

```json
{
  "type": "object",
  "properties": {
    "cd": {
      "type": "string",
      "description": "Existing directory to enter. Omit to read the current directory."
    }
  }
}
```
