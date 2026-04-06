variable "cidr_range" {
    type    = string
    default = "10.0.0.0/16"
}

variable "pub_cidr" {
    type =string
    default = "10.0.1.0/24"
}

variable "priv_cidr" {
    type =string
    default = "10.0.2.0/24"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "nexus"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}