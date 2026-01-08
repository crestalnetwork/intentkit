
export interface Activity {
    id: string;
    agent_id: string;
    agent_name: string; // Enriched field
    activity_type: string;
    description: string;
    created_at: string;
    details?: Record<string, unknown>;
}

export interface PostBrief {
    id: string;
    agent_id: string;
    agent_name: string; // Enriched field
    title: string;
    summary: string;
    created_at: string;
    updated_at: string;
    view_count: number;
}

export interface Post extends PostBrief {
    content: string; // Full markdown content
}
