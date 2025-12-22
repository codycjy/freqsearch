// Package web provides embedded frontend static files.
package web

import (
	"embed"
	"io/fs"
)

//go:embed dist/*
var embeddedFiles embed.FS

// GetFileSystem returns the embedded frontend files as an fs.FS.
// The returned filesystem has the "dist" prefix stripped.
func GetFileSystem() (fs.FS, error) {
	return fs.Sub(embeddedFiles, "dist")
}
