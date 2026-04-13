package shared

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// Shared HTTP client for media downloads (reuses TCP connections).
var mediaHTTPClient = &http.Client{Timeout: 2 * time.Minute}

// MaxMediaSize is the maximum allowed media file size (100 MB).
const MaxMediaSize = 100 * 1024 * 1024

// DownloadFromURL downloads a file from the given URL and returns its bytes.
// Returns an error if the file exceeds MaxMediaSize.
func DownloadFromURL(ctx context.Context, url string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create download request: %w", err)
	}
	resp, err := mediaHTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("download from url: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download returned status %d", resp.StatusCode)
	}

	// Limit read to prevent OOM from excessively large files
	limited := io.LimitReader(resp.Body, MaxMediaSize+1)
	data, err := io.ReadAll(limited)
	if err != nil {
		return nil, fmt.Errorf("read download body: %w", err)
	}
	if len(data) > MaxMediaSize {
		return nil, fmt.Errorf("file exceeds maximum size of %d bytes", MaxMediaSize)
	}
	return data, nil
}

// FilenameFromURL extracts a clean filename from a URL, stripping query parameters.
func FilenameFromURL(url string) string {
	// Find last path segment
	name := url
	if idx := lastIndexByte(name, '/'); idx >= 0 {
		name = name[idx+1:]
	}
	// Strip query parameters
	if idx := indexByte(name, '?'); idx >= 0 {
		name = name[:idx]
	}
	if name == "" {
		name = "file"
	}
	return name
}

// EnsureFileExtension appends an appropriate file extension to name
// if it doesn't already have one, based on content type detection of data.
func EnsureFileExtension(name string, data []byte) string {
	if dotIdx := lastIndexByte(name, '.'); dotIdx >= 0 && dotIdx < len(name)-1 {
		return name
	}
	ct := http.DetectContentType(data)
	ext := extensionForContentType(ct)
	if ext != "" {
		return name + "." + ext
	}
	return name
}

func extensionForContentType(ct string) string {
	switch {
	case strings.HasPrefix(ct, "image/jpeg"):
		return "jpg"
	case strings.HasPrefix(ct, "image/png"):
		return "png"
	case strings.HasPrefix(ct, "image/gif"):
		return "gif"
	case strings.HasPrefix(ct, "image/webp"):
		return "webp"
	case strings.HasPrefix(ct, "video/mp4"):
		return "mp4"
	case strings.HasPrefix(ct, "audio/mpeg"):
		return "mp3"
	default:
		return ""
	}
}

func lastIndexByte(s string, c byte) int {
	for i := len(s) - 1; i >= 0; i-- {
		if s[i] == c {
			return i
		}
	}
	return -1
}

func indexByte(s string, c byte) int {
	for i := 0; i < len(s); i++ {
		if s[i] == c {
			return i
		}
	}
	return -1
}
