-- Create story_circle table with proper column names
create table if not exists story_circle (
    id int4 primary key generated always as identity,
    date timestamp with time zone default timezone('utc'::text, now()) not null,
    is_current boolean default false,
    narrative jsonb
);

-- Add index on is_current for better query performance
create index if not exists story_circle_is_current_idx on story_circle(is_current); 