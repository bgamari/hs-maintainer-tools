let
  nixpkgs = import <nixpkgs> {};
in with nixpkgs;
let
  scripts = python3Packages.buildPythonPackage {
    pname = "hs-maintainer-tools";
    version = "1.0";
    src = ./.;
    propagatedBuildInputs = [ git curl cabal-install haskellPackages.haddock nix ];
  };
in scripts
