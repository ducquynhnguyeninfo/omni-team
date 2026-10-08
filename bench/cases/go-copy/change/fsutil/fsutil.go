package fsutil

import (
	"io"
	"os"
	"path/filepath"
)

// Exists reports whether path exists.
func Exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// CopyAll copies every file in srcs into dstDir.
func CopyAll(srcs []string, dstDir string) error {
	for _, src := range srcs {
		in, err := os.Open(src)
		if err != nil {
			return err
		}
		defer in.Close()

		out, err := os.Create(filepath.Join(dstDir, filepath.Base(src)))
		if err != nil {
			return err
		}
		defer out.Close()

		io.Copy(out, in)
	}
	return nil
}
