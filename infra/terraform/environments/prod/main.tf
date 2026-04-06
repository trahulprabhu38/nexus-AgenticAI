
module "vpc" {
    source = "../../modules/vpc"

    name_prefix  = var.cluster_name
 
    cidr_range   = "10.0.0.0/16"
    pub_cidr     = "10.0.1.0/24"
    priv_cidr    = "10.0.2.0/24"

    public_subnet_tags = {
        "kubernetes.io/role/elb"                    = "1"
        "kubernetes.io/cluster/${var.cluster_name}" = "shared"
        }

    private_subnet_tags = {
        "kubernetes.io/role/internal-elb"           = "1"
        "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    }

    tags = {
        Environment = var.environment
        Terraform   = "true"
        Project     = "nexus"
    }
}

