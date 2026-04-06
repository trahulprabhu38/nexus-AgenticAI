
module "vpc" {
    source = "../../modules/vpc"

    cidr_range = "10.0.0.0/16"
    pub_cidr   = "10.0.1.0/24"
    priv_cidr  = "10.0.2.0/24"
}