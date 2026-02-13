import { Button } from "@/components/ui/button";
import { Home, Search } from "lucide-react";

export default function NotFound() {
    return (
        <div className="container flex min-h-[60vh] flex-col items-center justify-center py-10">
            <div className="mx-auto max-w-md text-center">
                <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                    <Search className="h-8 w-8 text-muted-foreground" />
                </div>
                <h2 className="mb-2 text-2xl font-bold tracking-tight">
                    Page Not Found
                </h2>
                <p className="mb-6 text-muted-foreground">
                    The page you&apos;re looking for doesn&apos;t exist or has been moved.
                </p>
                <Button asChild>
                    <a href="/">
                        <Home className="mr-2 h-4 w-4" />
                        Back to Home
                    </a>
                </Button>
            </div>
        </div>
    );
}
