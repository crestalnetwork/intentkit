package shared

import (
	"bytes"
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

// S3Storage provides media upload to S3-compatible object storage.
// Safe for concurrent use.
type S3Storage struct {
	client *s3.Client
	bucket string
	cdnURL string // e.g. "https://example.com/static"
	env    string // e.g. "production", used as key prefix
}

// NewS3StorageFromEnv creates an S3Storage from standard environment variables.
// Returns nil if AWS_S3_BUCKET is not set (graceful degradation).
// Reads: AWS_S3_BUCKET, AWS_S3_ENDPOINT_URL, AWS_S3_REGION_NAME,
// AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY, AWS_S3_CDN_URL, ENV.
func NewS3StorageFromEnv() *S3Storage {
	bucket := os.Getenv("AWS_S3_BUCKET")
	if bucket == "" {
		slog.Warn("AWS_S3_BUCKET not set, S3 storage disabled")
		return nil
	}

	region := os.Getenv("AWS_S3_REGION_NAME")
	if region == "" {
		region = "us-east-1"
	}

	accessKey := os.Getenv("AWS_S3_ACCESS_KEY_ID")
	secretKey := os.Getenv("AWS_S3_SECRET_ACCESS_KEY")
	endpointURL := os.Getenv("AWS_S3_ENDPOINT_URL")
	cdnURL := strings.TrimRight(os.Getenv("AWS_S3_CDN_URL"), "/")
	if cdnURL == "" {
		slog.Warn("AWS_S3_CDN_URL not set, S3 storage disabled")
		return nil
	}
	env := os.Getenv("ENV")
	if env == "" {
		env = "local"
	}

	cfg, err := awsconfig.LoadDefaultConfig(context.Background(),
		awsconfig.WithRegion(region),
		awsconfig.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider(accessKey, secretKey, ""),
		),
	)
	if err != nil {
		slog.Error("Failed to load AWS config", "error", err)
		return nil
	}

	var client *s3.Client
	if endpointURL != "" {
		client = s3.NewFromConfig(cfg, func(o *s3.Options) {
			o.BaseEndpoint = aws.String(endpointURL)
			o.UsePathStyle = true
		})
	} else {
		client = s3.NewFromConfig(cfg)
	}

	slog.Info("S3 storage initialized", "bucket", bucket, "env", env)
	return &S3Storage{
		client: client,
		bucket: bucket,
		cdnURL: cdnURL,
		env:    env,
	}
}

// StoreMedia uploads media bytes to S3 and returns the CDN URL.
// key should be a relative path like "wechat/{teamID}/{id}.jpg".
// The final S3 key will be "{env}/{key}".
// If contentType is empty, it will be detected from the data.
func (s *S3Storage) StoreMedia(ctx context.Context, data []byte, key string, contentType string) (string, error) {
	if contentType == "" {
		contentType = http.DetectContentType(data)
	}

	fullKey := s.env + "/" + key

	_, err := s.client.PutObject(ctx, &s3.PutObjectInput{
		Bucket:      aws.String(s.bucket),
		Key:         aws.String(fullKey),
		Body:        bytes.NewReader(data),
		ContentType: aws.String(contentType),
	})
	if err != nil {
		return "", fmt.Errorf("s3 put object: %w", err)
	}

	cdnURL := s.cdnURL + "/" + fullKey
	return cdnURL, nil
}
