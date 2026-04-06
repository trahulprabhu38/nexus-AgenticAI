terraform {
  required_version = ">= 1.3"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

#vpc 
resource "aws_vpc" "vpc" {
  cidr_block       = var.cidr_range
  instance_tenancy = "default"
  enable_dns_support  = true
  enable_dns_hostnames = true
  tags = {
    Name = "nexus"
  }
}

#public subnet
resource "aws_subnet" "public_subnet" {
  vpc_id     = aws_vpc.vpc.id
  cidr_block = var.pub_cidr
  map_public_ip_on_launch = true
  
   tags = merge(
    var.tags,
    var.private_subnet_tags,
    {
      Name = "${var.name_prefix}-private"
      Type = "private"
    }
  )
}

#private subnet
resource "aws_subnet" "private_subnet" {
  vpc_id     = aws_vpc.vpc.id
  cidr_block = var.priv_cidr
 
  tags = merge(
    var.tags,
    var.private_subnet_tags,
    {
      Name = "${var.name_prefix}-private"
      Type = "private"
    }
  )
}

#igw
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name = "nexus"
  }
}


#nat
resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.eip_nat.id
  subnet_id     = aws_subnet.public_subnet.id

  tags = {
    Name = "nexus"
  }  
  depends_on = [aws_internet_gateway.igw]
}

#eip
resource "aws_eip" "eip_nat" {
  domain   = "vpc"
}


#public_route_table
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  
  tags = {
    Name = "nexus"
  }
}

#public_route_table_association
resource "aws_route_table_association" "public_rta" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}


#private_route_table
resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }
  
  tags = {
    Name = "nexus"
  }
}

#private_route_table_association
resource "aws_route_table_association" "private_rta" {
  subnet_id      = aws_subnet.private_subnet.id
  route_table_id = aws_route_table.private_rt.id
}