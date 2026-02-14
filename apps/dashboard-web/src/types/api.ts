export type User = {
  id: string;
  email: string;
};

export type Garment = {
  id: string;
  garment_type: string;
  crop_path: string;
  attributes: Record<string, unknown>;
};

export type Match = {
  id: string;
  garment_id: string | null;
  product_id: string;
  rank: number;
  similarity: number;
  match_group: string;
};

export type Capture = {
  id: string;
  user_id: string;
  created_at: string;
  image_path: string;
  status: string;
  error: string | null;
  global_attributes: Record<string, unknown> | null;
  garments: Garment[];
  matches: Match[];
};

export type Profile = {
  user_id: string;
  user_embedding_meta: Record<string, unknown>;
  radar_vector: Record<string, number>;
  brand_stats: Record<string, number>;
  color_stats: Record<string, number>;
  category_bias: Record<string, number>;
  updated_at: string | null;
};

export type RadarPoint = {
  id: string;
  created_at: string;
  radar_vector: Record<string, number>;
};
