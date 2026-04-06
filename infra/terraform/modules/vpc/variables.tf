variable "name_prefix" {
  description    = "Prefix for resource names"
  type           = string
}

variable "cidr_range" {
  description    = "CIDR block for VPC"
  type           = string
}

variable "pub_cidr" {
  description = "List of public subnet CIDR blocks"
  type    = string
}

variable "priv_cidr" {
  description = "List of private subnet CIDR blocks"
  type    = string
}

variable "public_subnet_tags" {
  description = "Additional tags for public subnets"
  type        = map(string)
  default     = {}
}

variable "private_subnet_tags" {
  description = "Additional tags for private subnets"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
