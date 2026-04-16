package shared

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"resty.dev/v3"
)

// MaxMediaSize is the maximum allowed media file size (100 MB).
const MaxMediaSize = 100 * 1024 * 1024

// Shared HTTP client for media downloads (reuses TCP connections).
// GET is idempotent; resty retries on transient 5xx/429 and transport errors by default.
var mediaHTTPClient = resty.New().
	SetTimeout(2 * time.Minute).
	SetRetryCount(2).
	SetRetryWaitTime(500 * time.Millisecond).
	SetRetryMaxWaitTime(3 * time.Second).
	SetResponseBodyLimit(MaxMediaSize)

// DownloadFromURL downloads a file from the given URL and returns its bytes.
// Returns an error if the file exceeds MaxMediaSize.
func DownloadFromURL(ctx context.Context, url string) ([]byte, error) {
	resp, err := mediaHTTPClient.R().
		SetContext(ctx).
		Get(url)
	if err != nil {
		if errors.Is(err, resty.ErrReadExceedsThresholdLimit) {
			return nil, fmt.Errorf("file exceeds maximum size of %d bytes", MaxMediaSize)
		}
		return nil, fmt.Errorf("download from url: %w", err)
	}
	if resp.StatusCode() != http.StatusOK {
		return nil, fmt.Errorf("download returned status %d", resp.StatusCode())
	}
	return resp.Bytes(), nil
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
	ext := ExtensionForContentType(ct)
	if ext != "" {
		return name + "." + ext
	}
	return name
}

// ExtensionForContentType returns a file extension for the given content type.
// Returns "" if the content type is not recognized.
func ExtensionForContentType(ct string) string {
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
