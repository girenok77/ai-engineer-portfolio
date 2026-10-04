CREATE TABLE `applications` (
	`id` text PRIMARY KEY NOT NULL,
	`job_id` text,
	`title` text NOT NULL,
	`company` text NOT NULL,
	`url` text NOT NULL,
	`status` text NOT NULL,
	`cv_id` text,
	`notes` text DEFAULT '' NOT NULL,
	`sent_at` text,
	`reply_at` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `applications_job_id_unique` ON `applications` (`job_id`);--> statement-breakpoint
CREATE INDEX `idx_applications_sent_at` ON `applications` (`sent_at`);--> statement-breakpoint
CREATE TABLE `cvs` (
	`id` text PRIMARY KEY NOT NULL,
	`application_id` text,
	`filename` text NOT NULL,
	`object_key` text NOT NULL,
	`text_key` text,
	`created_at` text NOT NULL,
	`kind` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `jobs` (
	`id` text PRIMARY KEY NOT NULL,
	`title` text NOT NULL,
	`company` text NOT NULL,
	`location` text NOT NULL,
	`url` text NOT NULL,
	`description` text NOT NULL,
	`published` text NOT NULL,
	`expires` text NOT NULL,
	`active` integer DEFAULT 1 NOT NULL,
	`score` integer DEFAULT 0 NOT NULL,
	`category` text NOT NULL,
	`reasons` text NOT NULL,
	`first_seen` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_jobs_active_score` ON `jobs` (`active`,`score`);--> statement-breakpoint
CREATE TABLE `replies` (
	`id` text PRIMARY KEY NOT NULL,
	`application_id` text NOT NULL,
	`subject` text NOT NULL,
	`body` text NOT NULL,
	`received_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `runs` (
	`id` text PRIMARY KEY NOT NULL,
	`kind` text NOT NULL,
	`at` text NOT NULL,
	`status` text NOT NULL,
	`message` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`day` text NOT NULL,
	`project` text NOT NULL,
	`started_at` text NOT NULL,
	`ended_at` text NOT NULL,
	`active_seconds` integer NOT NULL,
	`elapsed_seconds` integer NOT NULL,
	`input_tokens` integer,
	`cached_tokens` integer,
	`output_tokens` integer,
	`total_tokens` integer,
	`source` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_sessions_day` ON `sessions` (`day`);--> statement-breakpoint
CREATE TABLE `settings` (
	`key` text PRIMARY KEY NOT NULL,
	`value` text NOT NULL
);
