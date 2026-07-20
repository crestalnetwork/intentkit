import React, { useRef, useState } from "react";
import { WidgetProps } from "@rjsf/utils";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ImagePlus, Trash2, Loader2 } from "lucide-react";
import { agentApi } from "@/lib/api";
import { getImageUrl } from "@/lib/utils";

export const PictureWidget = (props: WidgetProps) => {
    const { id, value, onChange, disabled, readonly } = props;
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);

    const imageUrl = getImageUrl(value);

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!file.type.startsWith("image/")) {
            setUploadError("Please select an image file");
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            setUploadError("Image must be less than 5MB");
            return;
        }

        setUploadError(null);
        setIsUploading(true);
        try {
            const result = await agentApi.uploadPicture(file);
            onChange(result.path);
            // Reset file input so the same file can be re-selected
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        } catch (err) {
            setUploadError(err instanceof Error ? err.message : "Upload failed");
        } finally {
            setIsUploading(false);
        }
    };

    const handleRemove = () => {
        onChange("");
        setUploadError(null);
    };

    return (
        <div className="mb-4">
            <div className="flex items-center gap-4">
                <Avatar className="h-20 w-20">
                    {imageUrl ? (
                        <AvatarImage src={imageUrl} alt="Agent picture" />
                    ) : null}
                    <AvatarFallback className="bg-muted text-muted-foreground">
                        <ImagePlus className="h-8 w-8" />
                    </AvatarFallback>
                </Avatar>

                <div className="flex flex-col gap-2">
                    <div className="flex gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={disabled || readonly || isUploading}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            {isUploading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Uploading...
                                </>
                            ) : (
                                <>
                                    <ImagePlus className="mr-2 h-4 w-4" />
                                    {value ? "Change" : "Upload"}
                                </>
                            )}
                        </Button>
                        {value && (
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                disabled={disabled || readonly || isUploading}
                                onClick={handleRemove}
                            >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Remove
                            </Button>
                        )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        JPEG, PNG, GIF or WebP. Max 5MB.
                        Don&apos;t worry, if you don&apos;t upload an avatar, AI will automatically create one for you.
                    </p>
                    {uploadError && (
                        <p className="text-xs text-destructive">{uploadError}</p>
                    )}
                </div>
            </div>

            <input
                ref={fileInputRef}
                id={id}
                type="file"
                accept="image/jpeg,image/png,image/gif,image/webp"
                className="hidden"
                onChange={handleFileSelect}
                disabled={disabled || readonly}
            />
        </div>
    );
};
