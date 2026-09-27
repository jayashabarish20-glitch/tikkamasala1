variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "vpc_id" {
  type    = string
  default = "vpc-0f9106c73305b5ba8"
}

variable "subnet_id" {
  type    = string
  default = "subnet-0086415cd0144f9f9"
}

variable "key_name" {
  type    = string
  default = "rds"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}